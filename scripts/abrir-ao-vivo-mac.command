#!/bin/bash
# Abre o painel ao vivo num Chrome dedicado com autoplay de som liberado -- a radio toca sozinha
# com o painel so' aberto, sem ninguem precisar clicar na pagina (sem isso o Chrome bloqueia
# voz e musica ate' o primeiro clique; ver sondarAutoplayComSom em useLiveEngine.ts).
#
# Uso: duplo clique no Finder (producao), ou `./scripts/abrir-ao-vivo-mac.command [prod|dev|URL]`.
# Pra abrir sozinho quando o Mac liga: Ajustes do Sistema > Geral > Itens de Inicio > "+" e
# escolha este arquivo.
#
# O perfil do Chrome e' separado (a flag so' vale quando o Chrome abre do zero, e o Chrome do
# dia a dia normalmente ja esta aberto). Faca login no painel uma vez nesta janela -- a sessao
# fica salva no perfil.
case "${1:-${LOCUFY_AO_VIVO_URL:-prod}}" in
  prod|producao) URL="https://app.locufybr.com/live" ;;
  dev|desenvolvimento) URL="https://ecologic-rebeca-unedible.ngrok-free.dev/live" ;;
  *) URL="${1:-$LOCUFY_AO_VIVO_URL}" ;;
esac
PERFIL="$HOME/Library/Application Support/Locufy/chrome-ao-vivo"
mkdir -p "$PERFIL"

open -na "Google Chrome" --args \
  --user-data-dir="$PERFIL" \
  --autoplay-policy=no-user-gesture-required \
  --disable-background-timer-throttling \
  --disable-renderer-backgrounding \
  --disable-backgrounding-occluded-windows \
  --no-first-run \
  --no-default-browser-check \
  --app="$URL"
