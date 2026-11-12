# 06 — Integrações com os gerenciadores

| Provedor | Consulta (somente leitura) | Ação | Rede |
|---|---|---|---|
| Repositórios (pacman) | `pacman -Sl`, `pacman -Qq` (uma vez, ~220 ms) | `pamac-installer PACOTE`: a janela do Pamac revisa a transação e pede o Polkit | não |
| Flatpak | `flatpak remote-ls --cached` (~130 ms); sem cache, busca de novo | `flatpak install --system -y --noninteractive REMOTO ID`, com progresso real e cancelamento | só sem cache |
| AUR | RPC v5 (`/rpc/v5/info`, ~1 s): versão, votos, mantenedor, desatualizado | `pamac-installer --build PACOTE`: o Pamac oferece ler os arquivos de compilação | sim |
| Instalados | `.desktop` em `XDG_DATA_DIRS` e nos exports do Flatpak; `flatpak list` | `Gio.DesktopAppInfo.launch` / `flatpak run` | não |
| `.deb/.rpm` | — | `big-pkg-installer-gui ARQUIVO` (conversão), **depois** de mostrar o nativo | não |
| `.pkg.tar.*` | — | `pamac-installer ARQUIVO` | não |
| Steam | `steam` no PATH | `steam://store/ID` | — |
| Wine / Bottles | `wine` no PATH, Bottles instalado (Flatpak) | `wine ARQUIVO`, `wine msiexec /i`, `wine cmd /c`, `flatpak run com.usebottles.bottles ARQUIVO` | — |
| Java | `java` no PATH | `java -jar ARQUIVO` | — |

**Verificação do resultado:**

- `pacman -Q` depois do Pamac;
- `flatpak info` depois do Flatpak;
- "Lançado" quando o trabalho passa para outro programa (big-pkg-installer, Wine), porque não podemos saber como termina.

**Indisponibilidade** sempre aparece como opção desativada, com o motivo ("O Wine não está instalado", "O Flatpak não está instalado"). Fontes que não responderam aparecem em "Não consultados".
