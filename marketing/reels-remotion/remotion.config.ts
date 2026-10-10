import { Config } from "@remotion/cli/config";

// Serve marketing/reels como pasta pública: staticFile("V5/tela/cena-03.webm") etc.
Config.setPublicDir("../reels");
Config.setVideoImageFormat("jpeg");
Config.setCodec("h264");
