# 01 — Pesquisa dos projetos de referência

Revisões estudadas em 12/11/2026.

| Projeto | Licença | O que faz | O que aproveitamos |
|---|---|---|---|
| [zorin-exec-guard](https://github.com/ruscher/zorin-exec-guard) | GPL-3.0-or-later | GTK 3 + apt/aptdaemon. Ao abrir `.exe/.msi` (ou `.deb/.AppImage`), procura no app-db por **regex do nome do arquivo** e oferece o substituto (apt, Flatpak, link) ou executar. | O conceito (interceptar pelo tipo MIME e sugerir o nativo) e a ideia de alternativa. **Nenhum código copiado**: a interface, o modelo e a identificação são próprios. |
| [zorin-exec-guard-app-db](https://github.com/ruscher/zorin-exec-guard-app-db) | GPL-2.0-or-later | 241 entradas `{regex, name, flatpak, desktopLauncher, alternative, webLink, apt}`. | Ponto de partida do catálogo: cada entrada foi reescrita no nosso esquema, com globs no lugar das regex, pacotes do Arch no lugar do apt e IDs Flatpak conferidos. Créditos em `README.md`. |
| [big-pkg-installer](https://github.com/biglinux/big-pkg-installer) | GPL-2.0-or-later | GTK4/libadwaita; converte e instala `.deb/.rpm` (`big-pkg-installer-gui ARQUIVO`). | **Integração**, sem duplicar: o `.deb/.rpm` vai para ele, mas só depois de mostrarmos o equivalente nativo. |
| [big-executable](https://github.com/biglinux/big-executable) | GPL-3.0 | Diálogo yad "Executar arquivo" para `application/x-executable` e `x-shellscript` (com opção de root). | Mantido como está: não declaramos esses tipos, então não há conflito de associação. Nossa confirmação nunca oferece executar como root. |
| [rpmtoarch](https://github.com/biglinux/rpmtoarch) | (sem arquivo de licença) | Conversor `.rpm` antigo (yad + namcap). | Não usado: o big-pkg-installer já cobre `.rpm`. |
| [appimage-creator](https://github.com/big-comm/appimage-creator) | GPL-3.0 | Cria AppImages **a partir de aplicativos Linux**. | Não integrado na 0.1: não serve para localizar alternativas nem converter programas do Windows. Fica no roteiro como recurso avançado. |

## Ferramentas do sistema usadas

- **pacman** (`-Sl`, `-Qq`): repositórios e pacotes instalados, local e sem rede, 0,2 s.
- **pamac-installer**: instala dos repositórios e compila do AUR mostrando a transação (e os arquivos de compilação do AUR) e pedindo o Polkit. `pamac info --json` foi descartado: um nome inexistente faz o lote inteiro falhar.
- **AUR RPC v5**: votos, mantenedor, desatualizado. É a única consulta que exige rede.
- **flatpak** (`remote-ls --cached`, com nova busca se o cache do usuário estiver vazio).
- **XDG**: `.desktop` em `XDG_DATA_DIRS` e nos exports do Flatpak para saber o que já está instalado.
