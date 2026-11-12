# 09 — Testes

`make check` = validação do catálogo + **73 testes** (pytest, ~1 s). Mais `ruff check src tests tools`.

## Matriz da especificação

| Caso | Resultado esperado | Teste automatizado | Verificação real |
|---|---|---|---|
| `ChromeSetup.exe` | identifica o Chrome, sugere Linux | `test_chrome_setup` | instalador real (13 MB): provável, "Abrir programa instalado" (o Chrome está instalado aqui) |
| `DiscordSetup.exe` | Discord nativo/Flatpak | `test_discord_confirmed_by_metadata` | real (160 MB, Squirrel): confirmado, repositório extra + Flathub |
| `Firefox Setup.exe` | reconhece e vê se está instalado | `test_firefox_installed_opens_directly` | `Firefox Installer.exe` real: confirmado, abre o instalado |
| `Notepad++.exe` | editores equivalentes com diferenças | `test_notepadpp_alternatives_only` | `npp.Installer.x64.exe` real (NSIS): Kate/Geany/Notepad Next com notas |
| `SpotifySetup.exe` | opções Linux verificadas | `test_spotify` | real: confirmado, repositório + Flathub + AUR |
| Instalador desconhecido | aviso e opções seguras | `test_unknown_windows_installer` | — |
| `.deb` conhecido | nativo antes de converter | `test_deb_prefers_native_before_conversion` | `.deb` real do Chrome (cache do Pamac): confirmado |
| `.rpm` | caminho pelo big-pkg-installer | `test_rpm_uses_big_pkg_installer` | — |
| AppImage | informações e opção de executar | `test_appimage_runs_only_on_request`, `test_appimage_update_info` | interface no laboratório |
| `.sh` desconhecido | não executa sozinho | `test_unknown_script_never_recommended`, `test_script_hints_and_no_execution` | — |
| Extensão falsa | alerta | `test_fake_exe_html`, `test_disguised_executable_and_double_extension` | página 404 real salva como `.exe` |
| Nome malicioso | sem injeção | `test_malicious_name_stays_one_argument`, `test_wine_command_is_an_argument_list` | — |
| Arquivo inexistente / sem permissão | erro compreensível | `test_errors`, `test_cli_json` (código 2) | — |
| Sem Wine | não oferece como disponível | `test_without_wine`, `test_missing_wine` | este computador não tem Wine: opção desativada + "Instalar Wine" |
| Sem Flatpak | explica | `test_without_flatpak` | — |
| Sem internet | funciona com dados locais | `test_offline_aur_still_answers` | `--offline` |
| Já instalado | abre direto | `test_firefox_installed_opens_directly`, `test_installed_cli_tool_*` | Chrome, Firefox, Kate, 7zip |
| Duas correspondências | não escolhe | `test_ambiguous_does_not_choose`, `test_choosing_a_candidate` | — |
| Cancelar instalação | estado real | `test_flatpak_job_cancel_reports_real_state` | — |
| Claro e escuro | sem falhas | — | BigWindowMaker, OneStepBack-Dark, Adwaita escuro (capturas) |
| Wayland e X11 | fluxo correto | — | Window Maker (Xvfb) e wlmaker 35 aninhado |

## Outros testes

- **Robustez dos leitores:** `test_mutations_never_crash` faz 150 mutações em cada um de 6 formatos. Pegou um `NotImplementedError` do `zipfile`, já corrigido.
- **Arquivo trocado depois da análise:** `test_changed_file_is_refused` (conteúdo) e `test_replaced_file_same_content_other_inode_is_refused` (inode).
- **Catálogo:**
  - `test_schema_rejects` (9 casos), `test_alternatives_must_exist`, `test_overlay_invalid_is_ignored`, `test_shipped_catalog_is_valid`;
  - `test_catalog_globs_do_not_collide`: 422 nomes reais e 93 difíceis.
- **Associação:** `test_mime_associate_and_restore`, com um `mimeapps.list` que já tinha o Wine e o big-pkg-installer.
- **Privacidade:** `test_history_keeps_names_not_paths` (permissão 0600, sem `/home`).
- **Interface:** `test_idle_callbacks_are_not_bool_returning_methods`, regressão do laço de CPU 100% descrito abaixo.

## Laboratórios (nunca a tela real)

- **X11:** `Xvfb :91` + `wmaker` com `big-wm-firstrun x11`, HOME descartável, `systemctl/loginctl/reboot` bloqueados, D-Bus do sistema apontado para lugar nenhum.
- **Wayland:** wlmaker 35 aninhado (`WLR_BACKENDS=x11`), XWayland, mesmo isolamento.
- **Gerenciador de arquivos:**
  - `gio open arquivo.exe` e **Thunar** (Enter sobre `SpotifySetup.exe`) abriram o Big Trust Alt instalado. **Verificado.**
  - Arrastar de outro programa para a janela: **não verificado** (o código usa `Gtk.DropTarget` padrão).

## Desempenho (medido)

| Medida | Resultado |
|---|---|
| Janela inicial visível (X11, Xvfb) | 520 ms |
| Memória (RSS) em repouso | ~190 MiB com o renderizador padrão (Vulkan, em software no Xvfb); ~130 MiB com `GSK_RENDERER=cairo` |
| CPU em repouso | 0 ticks em 10 s, com e sem resultado |
| Catálogo (358 entradas) + índice | 24 ms + 24 ms |
| pacman / Flatpak / AUR | 220 ms / 130 ms / ~1 s (rede) |
| Identificação local | 0,4–22 ms por arquivo; com SHA-256 de 160 MB, 120 ms |

**Bug encontrado e corrigido pela medição:** `GLib.idle_add(button.grab_focus)` repetia para sempre, porque `grab_focus()` devolve `True`. Isso deixava a CPU em 100% com o resultado aberto.

## Não verificado

- Instalar de verdade pelo Pamac, pelo Flatpak ou pelo AUR a partir da interface: no laboratório não há agente Polkit, de propósito, para não alterar o sistema real. O fluxo (comando, verificação `pacman -Q`/`flatpak info`, cancelamento) está coberto pelos testes com processos simulados.
- O app aberto numa sessão gráfica real do usuário.
- KDE Plasma, GNOME e XFCE (sem dependência deles no código; não testado).
- `.msix`, `.rpm`, `.jar` e `.flatpakref` reais: só arquivos gerados nos testes.
