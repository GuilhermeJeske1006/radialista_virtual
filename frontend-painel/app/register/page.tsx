"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "../../lib/api";
import { RADIALISTA_VAZIO, Radialista } from "../../lib/types";
import { PLANOS, formatarReais } from "../../lib/planos";
import { LocufyLogo, LocufySpin } from "../../components/LocufyLogo";
import ThemeToggle from "../../components/ThemeToggle";
import { captureCampaign, trackFunnel } from "../../lib/funnel";
import CheckoutModal from "../../components/CheckoutModal";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type CampoErros = {
  nome?: string;
  email?: string;
  senha?: string;
  confirmarSenha?: string;
  nomeRadio?: string;
};

function validarNome(v: string) {
  return v.trim() ? "" : "Preencha seu nome";
}
function validarEmail(v: string) {
  if (!v) return "Preencha seu e-mail";
  if (!EMAIL_RE.test(v)) return "E-mail inválido";
  return "";
}
function validarSenha(v: string) {
  return v.length >= 8 ? "" : "A senha precisa ter pelo menos 8 caracteres";
}
function validarConfirmarSenha(senha: string, v: string) {
  return v === senha ? "" : "As senhas não conferem";
}
function validarNomeRadio(v: string) {
  return v.trim() ? "" : "Dá um nome pra sua rádio";
}
export default function RegisterPage() {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmarSenha, setConfirmarSenha] = useState("");
  const [nomeRadio, setNomeRadio] = useState("");
  const [planoId, setPlanoId] = useState("flex");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [mostrarCheckout, setMostrarCheckout] = useState(false);
  const [passo, setPasso] = useState<1 | 2 | 3>(1);
  const [campoErros, setCampoErros] = useState<CampoErros>({});
  const [tocado, setTocado] = useState<Record<keyof CampoErros, boolean>>({
    nome: false,
    email: false,
    senha: false,
    confirmarSenha: false,
    nomeRadio: false,
  });

  const headingRef = useRef<HTMLHeadingElement>(null);
  const initialStep = useRef(true);
  useEffect(() => {
    const selected = new URLSearchParams(window.location.search).get("plano");
    if (PLANOS.some(p => p.id === selected)) setPlanoId(selected!);
    captureCampaign();
    trackFunnel("register_started", { plano: PLANOS.some(p => p.id === selected) ? selected! : "flex" });
  }, []);
  useEffect(() => {
    if (initialStep.current) { initialStep.current = false; return; }
    headingRef.current?.focus();
  }, [passo]);

  function focarErro(erros: CampoErros) {
    const field = Object.entries(erros).find(([, value]) => value)?.[0];
    if (field) requestAnimationFrame(() => document.getElementById(field)?.focus());
  }

  function marcarTocado(campo: keyof CampoErros) {
    setTocado((t) => ({ ...t, [campo]: true }));
  }

  function onChangeNome(v: string) {
    setNome(v);
    setCampoErros((c) => ({ ...c, nome: validarNome(v) }));
  }
  function onChangeEmail(v: string) {
    setEmail(v);
    setCampoErros((c) => ({ ...c, email: validarEmail(v) }));
  }
  function onChangeSenha(v: string) {
    setSenha(v);
    setCampoErros((c) => ({
      ...c,
      senha: validarSenha(v),
      confirmarSenha: confirmarSenha ? validarConfirmarSenha(v, confirmarSenha) : c.confirmarSenha,
    }));
  }
  function onChangeConfirmarSenha(v: string) {
    setConfirmarSenha(v);
    setCampoErros((c) => ({ ...c, confirmarSenha: validarConfirmarSenha(senha, v) }));
  }
  function onChangeNomeRadio(v: string) {
    setNomeRadio(v);
    setCampoErros((c) => ({ ...c, nomeRadio: validarNomeRadio(v) }));
  }
  function validar(): boolean {
    const erros: CampoErros = {
      nome: validarNome(nome),
      email: validarEmail(email),
      senha: validarSenha(senha),
      confirmarSenha: validarConfirmarSenha(senha, confirmarSenha),
      nomeRadio: validarNomeRadio(nomeRadio),
    };
    setCampoErros(erros);
    setTocado({
      nome: true,
      email: true,
      senha: true,
      confirmarSenha: true,
      nomeRadio: true,
    });
    const primeiroErro = Object.values(erros).find((m) => m);
    if (primeiroErro) {
      setErro(primeiroErro);
      focarErro(erros);
      return false;
    }
    return true;
  }

  function validarPasso1(): boolean {
    const erros = {
      nome: validarNome(nome),
      email: validarEmail(email),
      senha: validarSenha(senha),
      confirmarSenha: validarConfirmarSenha(senha, confirmarSenha),
    };
    setCampoErros((c) => ({ ...c, ...erros }));
    setTocado((t) => ({ ...t, nome: true, email: true, senha: true, confirmarSenha: true }));
    const primeiroErro = Object.values(erros).find((m) => m);
    if (primeiroErro) {
      setErro(primeiroErro);
      focarErro(erros);
      return false;
    }
    setErro("");
    return true;
  }

  function validarPasso2(): boolean {
    const erros = { nomeRadio: validarNomeRadio(nomeRadio) };
    setCampoErros((c) => ({ ...c, ...erros }));
    setTocado((t) => ({ ...t, nomeRadio: true }));
    const primeiroErro = Object.values(erros).find((m) => m);
    if (primeiroErro) {
      setErro(primeiroErro);
      focarErro(erros);
      return false;
    }
    setErro("");
    return true;
  }

  function avancar() {
    if (passo === 1 && validarPasso1()) { trackFunnel("register_account_step", { plano: planoId }); setPasso(2); }
    else if (passo === 2 && validarPasso2()) { trackFunnel("register_radio_step", { plano: planoId }); setPasso(3); }
  }

  function voltar() {
    setErro("");
    if (passo === 2) setPasso(1);
    else if (passo === 3) setPasso(2);
  }

  async function concluir(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    if (passo !== 3) { avancar(); return; }
    if (!validar()) return;
    setCarregando(true);
    let contaCriada = false;
    try {
      // sessao ja vem via cookie httpOnly no Set-Cookie da resposta -- nada pra guardar aqui.
      await apiFetch("/auth/register", {
        method: "POST",
        body: JSON.stringify({ nome: nome.trim(), email, senha, campanha: captureCampaign() }),
      });
      contaCriada = true;

      await apiFetch("/config/radio", {
        method: "PUT",
        body: JSON.stringify({
          nome_radio: nomeRadio.trim(),
        }),
      });

      const radialistas = await apiFetch<Radialista[]>("/config/radialistas");
      const radialista = radialistas[0];
      if (radialista) {
        await apiFetch(`/config/radialistas/${radialista.id}`, {
          method: "PUT",
          body: JSON.stringify(RADIALISTA_VAZIO),
        });
      }

      // conta, radio e radialista prontos -- abre o checkout transparente embutido na
      // pagina; POST /billing/checkout so' e' chamado dentro do CheckoutModal.
      setMostrarCheckout(true);
      setCarregando(false);
    } catch (err) {
      if (contaCriada) {
        // conta ja existe (registro deu certo) -- mostrar "erro ao criar conta" aqui seria
        // enganoso e levaria a um retry que falha por e-mail duplicado. Manda pro dashboard,
        // que sinaliza a assinatura pendente.
        window.location.href = "/dashboard?onboarding=incompleto";
        return;
      }
      setErro(err instanceof ApiError ? err.message : "Erro ao criar conta");
      setCarregando(false);
    }
  }

  const formInvalido =
    !!validarNome(nome) ||
    !!validarEmail(email) ||
    !!validarSenha(senha) ||
    !!validarConfirmarSenha(senha, confirmarSenha) ||
    !!validarNomeRadio(nomeRadio);

  const PASSOS = ["Seus dados", "Sua rádio", "Seu plano"];
  const fields: { key: keyof CampoErros; label: string; type: string; value: string; change: (v: string) => void; autoComplete: string }[] = [
    { key: "nome", label: "Seu nome", type: "text", value: nome, change: onChangeNome, autoComplete: "name" },
    { key: "email", label: "E-mail", type: "email", value: email, change: onChangeEmail, autoComplete: "email" },
    { key: "senha", label: "Senha", type: "password", value: senha, change: onChangeSenha, autoComplete: "new-password" },
    { key: "confirmarSenha", label: "Confirmar senha", type: "password", value: confirmarSenha, change: onChangeConfirmarSenha, autoComplete: "new-password" },
  ];
  const inputClass = "w-full rounded-xl border border-border-strong bg-bg px-3 py-3 text-base text-fg focus:outline-none focus:ring-2 focus:ring-acento-claro";
  return (
    <main className="min-h-screen bg-bg flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-4xl">
        <div className="flex items-center justify-center gap-3 mb-6">
          <LocufyLogo wordmarkClassName="text-2xl" /><ThemeToggle />
        </div>
        <form noValidate onSubmit={concluir} className="bg-surface rounded-3xl border border-border-strong shadow-theme-sm p-5 sm:p-8">
          <ol aria-label="Etapas do cadastro" className="flex gap-3 mb-8">
            {PASSOS.map((label, i) => <li key={label} aria-current={passo === i + 1 ? "step" : undefined} className={`flex-1 text-sm border-b-2 pb-3 ${passo === i + 1 ? "border-acento-claro text-fg font-semibold" : "border-border text-fg/65"}`}>
              <span aria-hidden="true">{i + 1}. </span>{label}
            </li>)}
          </ol>
          <h1 ref={headingRef} tabIndex={-1} className="font-display text-xl font-bold text-fg mb-2 outline-none">
            {passo === 1 ? "Crie sua conta" : passo === 2 ? "Qual é o nome da sua rádio?" : "Confirme o plano da sua rádio"}
          </h1>
          <p className="text-sm text-fg/65 mb-6">{passo === 1 ? "Informe seus dados de acesso. Você escolhe o plano antes de pagar." : passo === 2 ? "Por enquanto, só precisamos do nome. Voz, programação e os outros dados podem ser configurados depois." : "O pagamento abre aqui mesmo, em um ambiente seguro. Confira os valores antes de confirmar."}</p>
          {passo === 1 && <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {fields.map(field => {
              const error = tocado[field.key] && campoErros[field.key];
              const help = field.key === "senha" ? "senha-ajuda" : undefined;
              return <div key={field.key}>
                <label htmlFor={field.key} className="block text-sm font-medium text-fg mb-2">{field.label}</label>
                <input id={field.key} name={field.key} type={field.type} required autoComplete={field.autoComplete} value={field.value}
                  minLength={field.type === "password" ? 8 : undefined}
                  onChange={e => field.change(e.target.value)} onBlur={() => { field.change(field.value); marcarTocado(field.key); }}
                  aria-invalid={!!error} aria-describedby={error ? `${field.key}-erro` : help} className={inputClass} />
                {error ? <p id={`${field.key}-erro`} className="mt-2 text-sm text-laranja">{error}</p> : field.key === "senha" && <p id="senha-ajuda" className="mt-2 text-sm text-fg/65">Use pelo menos 8 caracteres.</p>}
              </div>;
            })}
          </div>}
          {passo === 2 && <div className="max-w-lg">
            <label htmlFor="nomeRadio" className="block text-sm font-medium text-fg mb-2">Nome da rádio</label>
            <input id="nomeRadio" name="nomeRadio" required autoComplete="organization" value={nomeRadio} placeholder="Ex.: Rádio Cidade FM"
              onChange={e => onChangeNomeRadio(e.target.value)} onBlur={() => { onChangeNomeRadio(nomeRadio); marcarTocado("nomeRadio"); }}
              aria-invalid={!!(tocado.nomeRadio && campoErros.nomeRadio)} aria-describedby={tocado.nomeRadio && campoErros.nomeRadio ? "nomeRadio-erro" : undefined} className={inputClass} />
            {tocado.nomeRadio && campoErros.nomeRadio && <p id="nomeRadio-erro" className="mt-2 text-sm text-laranja">{campoErros.nomeRadio}</p>}
          </div>}
          {passo === 3 && <fieldset>
            <legend className="sr-only">Escolha seu plano mensal</legend>
            <div className="grid max-w-xl gap-4">
              {PLANOS.map(plano => <label key={plano.id} className={`relative cursor-pointer rounded-xl border p-4 focus-within:ring-2 focus-within:ring-acento-claro ${planoId === plano.id ? "border-acento-claro bg-bg" : "border-border-strong"}`}>
                <span className="flex items-center gap-2 font-semibold text-fg">
                  <input type="radio" name="plano" value={plano.id} checked={planoId === plano.id} onChange={() => { setPlanoId(plano.id); trackFunnel("plan_selected", { plano: plano.id }); }} className="accent-brand-500 h-5 w-5" />{plano.nome}
                </span>
                <span className="block text-sm text-fg/65 mt-2 min-h-12">{plano.descricao}</span>
                <span className="block text-2xl font-bold text-fg mt-4">R$ {formatarReais(plano.preco)}<span className="text-sm font-normal">/mês + uso</span></span>
                <span className="block text-sm text-fg mt-4">{plano.agentes} {plano.agentes === 1 ? "radialista virtual" : "radialistas virtuais"}</span>
                <span className="block text-sm text-fg mt-1">WhatsApp completo, sem franquia de mensagens</span>
                <span className="block text-sm text-fg mt-1">Até {plano.radialistasPorPrograma} {plano.radialistasPorPrograma === 1 ? "radialista" : "radialistas"} por programa</span>
                <span className="block text-sm text-fg mt-1">Clonagem de voz disponível</span>
              </label>)}
            </div>
            <p className="text-sm text-fg/65 mt-4">R$ 69,90 por mês + uso pós-pago. Sem franquia de mensagens. O preço do processamento usa as unidades e tarifas do modelo escolhido, com acréscimo de 100% sobre o custo de referência.</p>
          </fieldset>}
          {erro && <p role="alert" className="mt-5 text-sm text-laranja">{erro}</p>}
          <div className="flex justify-between gap-3 mt-8">
            {passo > 1 ? <button type="button" onClick={voltar} disabled={carregando} className="rounded-xl border border-border-strong px-4 py-3 text-fg">Voltar</button> : <span />}
            <button type="submit" disabled={carregando || (passo === 3 && formInvalido)} className="flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-3 text-sm font-semibold text-on-brand hover:bg-brand-600 disabled:opacity-60">
              {carregando ? <><LocufySpin size={14} /> Criando conta...</> : passo < 3 ? "Continuar" : "Criar conta e ir para pagamento"}
            </button>
          </div>
        </form>
        <p className="mt-6 text-center text-sm text-fg/65">Já tem conta? <Link href="/login" className="text-acento-claro underline">Entrar</Link></p>
        <p className="mt-3 text-center text-xs text-fg/65">Ao criar conta, você concorda com os <Link href="/termos" className="underline">Termos de Uso</Link> e a <Link href="/privacidade" className="underline">Política de Privacidade</Link>.</p>
        <CheckoutModal open={mostrarCheckout} onClose={() => { setMostrarCheckout(false); window.location.href = "/billing"; }} onSuccess={() => { window.location.href = "/dashboard"; }} endpoint="/billing/checkout" body={{ plano_id: planoId }} />
      </div>
    </main>
  );
}
