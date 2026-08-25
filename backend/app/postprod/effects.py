from pedalboard import Compressor, Distortion, HighpassFilter, Limiter, Pedalboard, PeakFilter, Reverb

# frequencia fixa de brilho (8kHz) -- so a intensidade (brightness_boost_db) varia por perfil,
# ver docs/plano-pos-producao-voz.md secao 3.2.
_BRIGHTNESS_FREQ_HZ = 8000.0


def montar_pipeline(perfil: dict) -> Pedalboard:
    """Monta a cadeia EQ -> compressao -> saturacao -> reverb -> limitador de um perfil de estilo."""
    eq = perfil["eq"]
    comp = perfil["compression"]
    sat = perfil["saturation"]
    rev = perfil["reverb"]

    return Pedalboard(
        [
            HighpassFilter(cutoff_frequency_hz=eq["high_pass_hz"]),
            PeakFilter(cutoff_frequency_hz=eq["presence_freq_hz"], gain_db=eq["presence_boost_db"], q=1.0),
            PeakFilter(cutoff_frequency_hz=_BRIGHTNESS_FREQ_HZ, gain_db=eq["brightness_boost_db"], q=0.7),
            Compressor(
                threshold_db=comp["threshold_db"],
                ratio=comp["ratio"],
                attack_ms=comp["attack_ms"],
                release_ms=comp["release_ms"],
            ),
            Distortion(drive_db=sat["drive_db"]),
            Reverb(room_size=rev["room_size"], wet_level=rev["wet_level"], dry_level=1 - rev["wet_level"]),
            Limiter(threshold_db=-1.0, release_ms=100),
        ]
    )
