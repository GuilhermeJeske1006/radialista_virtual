"""Teste funcional real, sem alterar preferências ou criar vozes.

Em backend: PYTHONPATH=. .venv/bin/python scripts/validar_melhorias_voz.py --output /tmp/voz-validacao
Acrescente --executar-api para gerar os quatro arquivos e uma página de escuta.
"""
import base64, html, json, subprocess, time
from pathlib import Path
import argparse
parser = argparse.ArgumentParser(description="Valida modelos, perfis e formatos com quatro sínteses reais.")
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--executar-api', action='store_true', help='Consome créditos em quatro sínteses, sem criar vozes.')
args = parser.parse_args()
if not args.executar_api:
    print('Prévia: quatro sínteses, v3 atual/neutro, v2 neutro e Flash neutro; MP3 128/192, buffered/streaming. Use --executar-api para consumir créditos.')
    raise SystemExit(0)
from app.config.settings import settings
from app.tts import client as tts
pasta=args.output
pasta.mkdir(exist_ok=False)
meta=tts.obter_metadados_voz(settings.elevenlabs_voice_id)
if not meta: raise SystemExit('Não foi possível confirmar a categoria da voz.')
texto='Boa tarde! Aqui é a Locufy. São 14:30, na frequência 87,5 FM. A promoção de hoje custa R$ 29,90. No dia 10/09/2026, tem música e companhia pra você.'
result={'categoria':meta['categoria'],'referencia_humana':False,'texto':texto,'sinteses':[]}
casos=[('v3-atual','eleven_v3','atual','mp3_44100_128',False),('v3-neutra','eleven_v3','natural','mp3_44100_192',True),('v2-neutra','eleven_multilingual_v2','natural','mp3_44100_192',False),('flash-neutra','eleven_flash_v2_5','natural','mp3_44100_128',True)]
cards=[]
for nome,modelo,perfil,formato,stream in casos:
 item={'nome':nome,'modelo':modelo,'perfil':perfil,'formato':formato,'streaming':stream}
 inicio=time.perf_counter()
 try:
  kwargs=dict(modelo=modelo,perfil=perfil,formato=formato,pronuncias={'Locufy':'Locufai'},eh_clonada=meta['categoria']=='cloned',tipo_bloco='comentario',tom='neutro')
  data=b''.join(tts.sintetizar_audio_stream(texto,**kwargs)) if stream else tts.sintetizar_audio(texto,max_tentativas=1,**kwargs)
  item['sintese_segundos']=round(time.perf_counter()-inicio,3)
  file=pasta/f'{nome}.mp3';file.write_bytes(data)
  probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,bit_rate:stream=sample_rate,channels','-of','json',str(file)],capture_output=True,check=True).stdout)
  subprocess.run(['ffmpeg','-v','error','-i',str(file),'-f','null','-'],capture_output=True,check=True)
  item.update(status='ok',bytes=len(data),duracao_segundos=float(probe['format']['duration']),bit_rate=probe['format']['bit_rate'],sample_rate=probe['streams'][0]['sample_rate'])
  b64=base64.b64encode(data).decode()
  cards.append(f'<article><h2>{html.escape(nome)}</h2><audio controls src="data:audio/mpeg;base64,{b64}"></audio><pre>{html.escape(json.dumps(item,indent=2))}</pre></article>')
 except Exception as exc:
  item.update(status='falhou',erro=type(exc).__name__,http_status=getattr(getattr(exc,'response',None),'status_code',None))
 result['sinteses'].append(item)
 (pasta/'resultados.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(item),flush=True)
(pasta/'escuta.html').write_text('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Validação das melhorias de voz</title><style>body{font:17px/1.5 system-ui;max-width:900px;margin:30px auto;padding:20px}article{border:1px solid #aaa;border-radius:12px;padding:20px;margin:20px 0}audio{width:100%}pre{white-space:pre-wrap}</style><h1>Validação das melhorias de voz</h1><p>Áudio sintético com a voz já configurada. Teste funcional dos modelos e formatos; não determina um vencedor em realismo. Os áudios são originais, sem equalizar volumes.</p><p>'+html.escape(texto)+'</p>'+''.join(cards)+'</html>')
if any(i['status']!='ok' for i in result['sinteses']): raise SystemExit(1)
