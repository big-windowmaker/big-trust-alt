# 12 — Relatório de entrega (0.1.0, 12/11/2026)

**Repositório:** https://github.com/big-windowmaker/big-trust-alt. Tag `v0.1.0`; CI verde em `main` e na tag.

## Implementado (verificado)

- **Detecção sem execução:** PE, MSI, MSIX/AppX, ELF/AppImage, deb, rpm, pacote Arch, jar, scripts, `.bat/.cmd/.ps1`, flatpakref, tar/zip. Conferida com instaladores reais: Chrome, Discord, Firefox, Notepad++, Spotify, 7-Zip, PuTTY e o `.deb` do Chrome.
- **Catálogo:** 358 entradas verificadas, esquema v1 com validador, sobreposição local validada, teste de colisão com 515 nomes.
- **Resolvedor:** instalado → repositórios → Flathub → Steam → AUR → site → alternativas → Wine. Ambíguo nunca escolhe. Um programa de terminal já instalado é reconhecido.
- **Interface GTK4/libadwaita:** recomendação explicada, opções rotuladas, confirmação para executar, detalhes técnicos, busca sem arquivo, histórico, preferências, associação reversível, relatório de identificação errada.
- **CLI:** `--analyze`, `--search`, `--json`, `--offline`, `--associate/--dissociate`, `--diagnostics`.
- **Traduções:** pt_BR, 247 mensagens, 0 faltando. O catálogo também é bilíngue.
- **Pacote:** PKGBUILD validado com `makepkg` e `namcap`; instalado no host, removido e reinstalado.

## Integrações

| Integração | Estado |
|---|---|
| X11 (Window Maker) e Wayland (wlmaker 35) | verificado em laboratório |
| Thunar / GIO abrindo `.exe` | verificado em laboratório |
| pacman, Flatpak, AUR (consulta) | verificado |
| Pamac / Flatpak (instalação real pela interface) | **não verificado**: no laboratório não há Polkit, de propósito |
| big-pkg-installer | comando verificado; conversão não executada |

## Testes

73 testes automatizados passando, ruff limpo, CI no container Arch.

## Problemas encontrados durante a entrega (corrigidos)

1. CPU em 100% com o resultado aberto (`idle_add(grab_focus)`).
2. `zipfile` levantando `NotImplementedError` com arquivo malformado (achado pelo teste de mutação).
3. O Flathub sumia para um usuário sem cache do Flatpak.
4. 7zip instalado (sem `.desktop`) fazia recomendar outro programa.
5. Selos ilegíveis no OneStepBack-Dark.
6. Diálogos sem fundo no tema BigWindowMaker. Contornado no app; a correção de fato pertence ao tema.

## Limites conhecidos

Ver [09-tests.md](09-tests.md#não-verificado) e [11-roadmap.md](11-roadmap.md).
