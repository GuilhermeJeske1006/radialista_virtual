@echo off
rem Abre o painel ao vivo num Chrome dedicado com autoplay de som liberado -- a radio toca
rem sozinha com o painel so' aberto, sem ninguem precisar clicar na pagina.
rem Uso: duplo clique (producao), ou "abrir-ao-vivo-windows.bat [prod|dev|URL]".
rem Pra abrir sozinho ao ligar o PC: Win+R, "shell:startup", e cole um atalho deste arquivo la'.
rem Faca login no painel uma vez nesta janela -- a sessao fica salva no perfil dedicado.
set "URL=%~1"
if "%URL%"=="" set "URL=prod"
if /i "%URL%"=="prod" set "URL=https://app.locufybr.com/live"
if /i "%URL%"=="producao" set "URL=https://app.locufybr.com/live"
if /i "%URL%"=="dev" set "URL=https://ecologic-rebeca-unedible.ngrok-free.dev/live"
if /i "%URL%"=="desenvolvimento" set "URL=https://ecologic-rebeca-unedible.ngrok-free.dev/live"
set "PERFIL=%LOCALAPPDATA%\Locufy\chrome-ao-vivo"
if not exist "%PERFIL%" mkdir "%PERFIL%"
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
start "" "%CHROME%" --user-data-dir="%PERFIL%" --autoplay-policy=no-user-gesture-required --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --no-first-run --no-default-browser-check --app="%URL%"
