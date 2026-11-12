# Changelog

## 0.1.0 — 2026-11-12

Primeira versão.

- Identificação pelo conteúdo (sem executar): PE/.exe (version info, .NET, assinatura, instalador), MSI, MSIX/AppX, ELF/AppImage, .deb, .rpm, pacotes do Arch, .jar, scripts, .bat/.cmd/.ps1, .flatpakref, tar/zip.
- Avisos: extensão falsa ou dupla, nome com caracteres invisíveis, arquitetura diferente, indícios em scripts, arquivo alterado depois da análise.
- Catálogo próprio, esquema v1 validado: 358 entradas verificadas, a partir da Zorin Exec Guard App DB e da lista do projeto.
- Opções: aplicativo instalado, repositórios (Pamac), Flathub, AUR (com aviso), site oficial, Steam, big-pkg-installer para .deb/.rpm, Wine/Bottles/Java só por escolha e com confirmação.
- Interface GTK4/libadwaita: recomendação explicada, alternativas rotuladas, detalhes técnicos, busca sem arquivo, histórico, preferências, associação de arquivos reversível.
- CLI: `--analyze`, `--search`, `--json`, `--offline`, `--associate/--dissociate`, `--diagnostics`.
- Traduções pt_BR e en.
