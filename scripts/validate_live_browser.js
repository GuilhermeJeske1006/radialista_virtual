/*
 * End-to-end diagnostic for Locufy's live radio screen.
 *
 * Run it through the local Playwright skill runner so `playwright` is available:
 *   cd /Users/guilhermejeske/.agents/skills/playwright
 *   LOCUFY_EMAIL='...' LOCUFY_PASSWORD='...' \
 *     node run.js /Users/guilhermejeske/projetos/locufy/scripts/validate_live_browser.js
 *
 * Optional variables:
 *   LOCUFY_URL=http://localhost:3001
 *   LOCUFY_PROGRAM_NAME='Nome do programa'
 *   OBSERVE_MS=45000
 *   HEADLESS=1
 *   OUTPUT_DIR=/private/tmp/locufy-live-validation
 */

const fs = require('node:fs');
const path = require('node:path');

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  console.error('Playwright nao foi encontrado. Rode este arquivo pelo runner indicado no cabecalho.');
  process.exit(2);
}

const baseUrl = (process.env.LOCUFY_URL || 'http://localhost:3001').replace(/\/$/, '');
const email = process.env.LOCUFY_EMAIL;
const password = process.env.LOCUFY_PASSWORD;
const observeMs = Number.parseInt(process.env.OBSERVE_MS || '45000', 10);
const outputDir = process.env.OUTPUT_DIR || path.join('/private/tmp', 'locufy-live-validation');
const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
const reportPath = path.join(outputDir, `report-${timestamp}.json`);
const screenshotPath = path.join(outputDir, `live-${timestamp}.png`);

if (!email || !password) {
  console.error('Defina LOCUFY_EMAIL e LOCUFY_PASSWORD antes de executar o teste.');
  process.exit(2);
}

fs.mkdirSync(outputDir, { recursive: true });

const report = {
  startedAt: new Date().toISOString(),
  baseUrl,
  observeMs,
  login: { ok: false },
  live: { started: false, observed: false },
  endpoints: [],
  consoleErrors: [],
  pageErrors: [],
  failedRequests: [],
  browserSpeechCalls: 0,
  audio: { playCalls: 0, playFailures: [], elements: [] },
  visibleWarnings: [],
  outcome: 'not-run',
};
const endpointTasks = [];

class ValidationStop extends Error {}

function endpointKind(url) {
  // real shape e' /live/{radialistaId}/programas/{programaId}/proxima e /live/{radialistaId}/tts --
  // um match por substring literal ("/live/proxima", "/live/tts") nunca bate por causa do id no meio.
  if (/\/live\/\d+\/programas\/\d+\/proxima(?:[/?]|$)/.test(url)) return 'next-speech';
  if (/\/live\/\d+\/tts(?:[/?]|$)/.test(url)) return 'tts';
  return null;
}

async function waitFor(predicate, timeoutMs, intervalMs = 250) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return true;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return false;
}

async function main() {
  const browser = await chromium.launch({ headless: process.env.HEADLESS === '1' });
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.addInitScript(() => {
    window.__locufyValidation = {
      browserSpeechCalls: 0,
      audioPlayCalls: 0,
      audioPlayFailures: [],
    };

    const originalSpeak = window.speechSynthesis?.speak?.bind(window.speechSynthesis);
    if (originalSpeak) {
      window.speechSynthesis.speak = (...args) => {
        window.__locufyValidation.browserSpeechCalls += 1;
        return originalSpeak(...args);
      };
    }

    const originalPlay = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function patchedPlay(...args) {
      window.__locufyValidation.audioPlayCalls += 1;
      const result = originalPlay.apply(this, args);
      if (result?.catch) {
        result.catch((error) => {
          window.__locufyValidation.audioPlayFailures.push(String(error?.message || error));
        });
      }
      return result;
    };
  });

  page.on('console', (message) => {
    if (message.type() === 'error') report.consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => report.pageErrors.push(String(error.message || error)));
  page.on('requestfailed', (request) => {
    report.failedRequests.push({ url: request.url(), failure: request.failure()?.errorText || 'unknown' });
  });
  page.on('response', async (response) => {
    const kind = endpointKind(response.url());
    if (!kind) return;

    endpointTasks.push((async () => {
      const item = {
        kind,
        status: response.status(),
        url: response.url(),
        receivedAt: new Date().toISOString(),
      };
      try {
        const body = await response.json();
        item.audioStatus = body.audio_status;
        item.audioError = body.audio_erro;
        item.speechLength = typeof body.fala === 'string' ? body.fala.length : 0;
        item.hasAudio = Boolean(body.audio_base64);
      } catch {
        item.body = 'non-json-or-unavailable';
      }
      report.endpoints.push(item);
    })());
  });

  try {
    await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.getByLabel('E-mail').fill(email);
    await page.getByLabel('Senha', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Entrar' }).click();

    report.login.ok = await waitFor(() => !page.url().includes('/login'), 15_000);
    report.login.url = page.url();
    if (!report.login.ok) {
      report.login.reason = 'A tela nao saiu de /login em 15 segundos.';
      report.outcome = 'login-failed-or-stalled';
      throw new ValidationStop();
    }

    await page.goto(`${baseUrl}/live`, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    const startButton = page.getByRole('button', { name: 'Comecar transmissao' });
    const programName = process.env.LOCUFY_PROGRAM_NAME;

    // Selecao de programa e' um <select> nativo (nao cards clicaveis) -- escolhe pelo nome
    // pedido via env ou, na falta dele, a primeira opcao real (indice 0 e' sempre o placeholder
    // "Selecione um programa").
    const programSelect = page.locator('select').first();
    if (await programSelect.isVisible().catch(() => false)) {
      if (programName) {
        await programSelect.selectOption({ label: new RegExp(programName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).catch(() => undefined);
      }
      const selecionado = await programSelect.evaluate((el) => el.selectedIndex);
      if (!selecionado) {
        await programSelect.selectOption({ index: 1 }).catch(() => undefined);
      }
    }

    if (!(await startButton.isVisible().catch(() => false))) {
      report.live.reason = 'Nenhum programa pronto para transmissao foi encontrado na tela /live.';
      report.outcome = 'program-not-ready';
      throw new ValidationStop();
    }

    await startButton.click();
    report.live.started = true;
    report.live.observed = await waitFor(
      () => report.endpoints.some((item) => item.kind === 'next-speech'),
      Math.min(observeMs, 20_000),
    );

    if (observeMs > 20_000) {
      await page.waitForTimeout(observeMs - 20_000);
    }

    report.visibleWarnings = await page.locator('body').evaluate((body) => {
      const text = body.innerText;
      return [
        'Fala pulada',
        'Voz IA indisponivel',
        'Usando fala local',
        'Tempo esgotado',
      ].filter((warning) => text.includes(warning));
    });

    const browserData = await page.evaluate(() => ({
      validation: window.__locufyValidation,
      elements: [...document.querySelectorAll('audio')].map((audio) => ({
        currentTime: audio.currentTime,
        duration: audio.duration,
        ended: audio.ended,
        paused: audio.paused,
        readyState: audio.readyState,
        src: audio.currentSrc || audio.src,
      })),
    }));
    report.browserSpeechCalls = browserData.validation.browserSpeechCalls;
    report.audio.playCalls = browserData.validation.audioPlayCalls;
    report.audio.playFailures = browserData.validation.audioPlayFailures;
    report.audio.elements = browserData.elements;

    await Promise.all(endpointTasks);
    const nextSpeech = report.endpoints.filter((item) => item.kind === 'next-speech');
    // audio_status vem do backend em portugues ('falhou'), nao em ingles -- comparar com
    // 'failed' nunca batia e deixava falha real de sintese passar como sucesso.
    const endpointFailure = nextSpeech.some((item) => item.status >= 400 || item.audioStatus === 'falhou');
    if (!nextSpeech.length) report.outcome = 'no-next-speech-response';
    else if (endpointFailure) report.outcome = 'tts-or-generation-failed';
    else if (report.browserSpeechCalls) report.outcome = 'browser-speech-fallback-detected';
    else if (!report.audio.playCalls) report.outcome = 'no-audio-playback-detected';
    else report.outcome = 'passed';
  } catch (error) {
    if (!(error instanceof ValidationStop)) {
      report.outcome = 'unexpected-error';
      report.error = String(error.message || error);
    }
  } finally {
    report.finishedAt = new Date().toISOString();
    await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => undefined);
    fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
    await browser.close();
  }

  console.log(`Resultado: ${report.outcome}`);
  console.log(`Relatorio: ${reportPath}`);
  console.log(`Screenshot: ${screenshotPath}`);
  console.log(`Respostas /live/proxima: ${report.endpoints.filter((item) => item.kind === 'next-speech').length}`);
  console.log(`Chamadas de fala nativa: ${report.browserSpeechCalls}`);
  process.exitCode = report.outcome === 'passed' ? 0 : 1;
}

main();
