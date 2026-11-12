<p align="center">
  <img src="data/icons/hicolor/scalable/apps/io.github.big_windowmaker.BigTrustAlt.svg" width="112" alt="">
</p>

<h1 align="center">Big Trust Alt</h1>

<p align="center">
  <b>A maneira inteligente de abrir, instalar e encontrar alternativas para programas no Linux.</b><br>
  Parte do <a href="https://github.com/big-windowmaker">Big WindowMaker</a> · feito para o <a href="https://www.biglinux.com.br">BigLinux</a>
</p>

<p align="center">
  <a href="https://github.com/big-windowmaker/big-trust-alt/actions/workflows/ci.yml"><img src="https://github.com/big-windowmaker/big-trust-alt/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/licen%C3%A7a-GPL--3.0--or--later-blue" alt="GPL-3.0-or-later">
  <img src="https://img.shields.io/badge/GTK4-libadwaita-4a86cf" alt="GTK4 + libadwaita">
  <img src="https://img.shields.io/badge/X11%20%2B%20Wayland-testado-success" alt="X11 e Wayland">
</p>

---

Você baixou `ChromeSetup.exe`, `DiscordSetup.exe` ou `npp.8.9.Installer.x64.exe` e deu dois cliques.
Em vez de um erro, ou de o Wine abrir sem perguntar nada, o **Big Trust Alt** mostra **o que o arquivo é**
e **a melhor maneira de ter esse programa no BigLinux**: o pacote dos repositórios, o Flatpak, o
AUR, o download oficial para Linux, um programa diferente com a mesma finalidade ou, se você
escolher, o próprio arquivo com o Wine.

**Nada é executado durante a análise.**

<p align="center">
  <img src="docs/screenshots/discord-x11.png" width="49%" alt="DiscordSetup.exe identificado: instalar a versão Linux dos repositórios">
  <img src="docs/screenshots/notepadpp-escuro.png" width="49%" alt="Notepad++: alternativas funcionais no tema escuro">
</p>

## ✨ O que ele faz

- 🔎 **Identifica pelo conteúdo, não pela extensão.** Lê os dados internos de `.exe` (version info, .NET, assinatura, tipo de instalador), `.msi`, `.msix/.appx`, `.deb`, `.rpm`, AppImage, pacotes do Arch, `.jar`, scripts, `.flatpakref` e arquivos compactados, sem executá-los.
- 🧭 **Recomenda o melhor caminho para o BigLinux.** Mostra se você já tem o programa, se ele está nos repositórios, no Flathub, no AUR ou no site oficial, e explica o porquê.
- 🔁 **Mostra alternativas honestas.** O Photoshop leva ao GIMP e ao Krita, com o aviso de que *não são* o Photoshop. Lançadores de jogos levam ao Heroic, ao Lutris ou ao Steam.
- 🛡️ **Avisa sobre o que importa.** Extensão falsa (`fatura.pdf.exe`), nome com caracteres invisíveis, programa feito para outro processador, script que baixa e executa código, ou arquivo que mudou depois da análise.
- 🍷 **Não tira a sua escolha.** O Wine, o Bottles e a execução do próprio arquivo continuam à vista, sempre com confirmação e sempre com o aviso de que o Wine não isola nada.
- 📦 **Integra o que o BigLinux já tem.** O Pamac instala dos repositórios e compila do AUR, com a revisão da transação. O Flatpak instala do Flathub, com progresso real. O [big-pkg-installer](https://github.com/biglinux/big-pkg-installer) converte `.deb/.rpm`, mas só depois de mostrar se há um pacote nativo.
- 🌐 **Funciona sem internet** com o catálogo local e os repositórios do sistema. Só o AUR precisa de rede.
- 🔒 **Privado.** Nada é enviado. O histórico fica só no seu computador e guarda apenas o nome do arquivo.

<p align="center">
  <img src="docs/screenshots/busca.png" width="32%" alt="Procurar alternativa para o Adobe Photoshop">
  <img src="docs/screenshots/confirmacao.png" width="32%" alt="Confirmação antes de executar um AppImage">
  <img src="docs/screenshots/spotify-wayland.png" width="32%" alt="SpotifySetup.exe no Big WindowMaker Wayland">
</p>

## 📥 Instalação

### Pacote (BigLinux, Manjaro, Arch)

O PKGBUILD fica em [`pkgbuild/PKGBUILD`](pkgbuild/PKGBUILD):

```bash
git clone https://github.com/big-windowmaker/big-trust-alt.git
cd big-trust-alt/pkgbuild
makepkg -si
```

Dependências: `python`, `python-gobject`, `gtk4`, `libadwaita`, `pacman`.
Opcionais: `pamac-gtk` (instalar dos repositórios e do AUR), `flatpak`, `big-pkg-installer`
(`.deb/.rpm`), `wine` e `jre-openjdk`.

### Direto do código (sem instalar)

```bash
make build                       # compila as traduções
PYTHONPATH=src python3 -m big_trust_alt ~/Downloads/ChromeSetup.exe
```

## 🚀 Uso

- **Dois cliques** num `.exe` ou `.msi` no gerenciador de arquivos. Para tornar o Big Trust Alt o padrão desses tipos, vá em *Preferências → Abrir programas do Windows com o Big Trust Alt*. A opção guarda as escolhas anteriores e as devolve quando você a desliga.
- **Arraste** um arquivo para a janela, ou use *Abrir arquivo…* (`Ctrl+O`).
- **Sem arquivo:** *Procurar alternativa…* (`Ctrl+F`), por exemplo "Photoshop" ou "WinRAR".
- **Terminal:**

```bash
big-trust-alt --analyze ~/Downloads/DiscordSetup.exe        # resultado legível
big-trust-alt --analyze arquivo.msi --json --offline         # JSON, sem consultar o AUR
big-trust-alt --search "notepad++"
big-trust-alt --associate | --dissociate | --associations
big-trust-alt --diagnostics                                  # relatório sem dados pessoais
```

## 🧩 Como funciona

```
arquivo ─▶ detectores (só leitura) ─▶ catálogo + pontuação ─▶ provedores (pacman, Flatpak, AUR, instalados)
        ─▶ opções ordenadas + recomendada ─▶ janela ou JSON ─▶ ação escolhida (Pamac, Flatpak, big-pkg-installer, Wine)
```

- **Catálogo:** 358 entradas verificadas em `data/app-db/catalog/`, com esquema versionado e validado.
- **Correspondência:** confirmada, provável, ambígua (você escolhe) ou não identificada.
- **Documentação técnica:** [`docs/`](docs/):
  - [arquitetura](docs/02-architecture.md)
  - [segurança](docs/03-security.md)
  - [catálogo](docs/04-app-database.md)
  - [detecção](docs/05-file-detection.md)
  - [testes](docs/09-tests.md)

## 🤝 Contribuir

O jeito mais útil de ajudar é **melhorar o catálogo**. Encontrou um programa que não foi
reconhecido, ou foi reconhecido errado?

1. No resultado, clique em **Informar identificação errada**. O relatório (sem pastas nem dados pessoais) vai para a área de transferência.
2. Abra uma [issue](https://github.com/big-windowmaker/big-trust-alt/issues/new/choose) com ele, ou corrija o JSON em `data/app-db/catalog/` e abra um PR.

Para código, veja [CONTRIBUTING.md](CONTRIBUTING.md). Antes do PR:

```bash
make check     # catálogo + 73 testes
make lint      # ruff
```

## 🙏 Agradecimentos

- **[Zorin Exec Guard](https://github.com/ruscher/zorin-exec-guard)** e **[Zorin Exec Guard App DB](https://github.com/ruscher/zorin-exec-guard-app-db)**, da Zorin OS Technologies Ltd. (GPL-3.0+ / GPL-2.0+). A ideia original e a base de 241 mapeamentos: 247 das nossas entradas partiram dela, reescritas e conferidas.
- **[big-pkg-installer](https://github.com/biglinux/big-pkg-installer)** e **[big-executable](https://github.com/biglinux/big-executable)**: Bruno Gonçalves, Tales A. Mendonça e a comunidade BigLinux.
- **[Pamac](https://github.com/manjaro/pamac)**, **[Flatpak](https://flatpak.org)/[Flathub](https://flathub.org)**, o **[AUR](https://aur.archlinux.org)** e o **[Wine](https://www.winehq.org)**.
- **Bruno Gonçalves** ([BigLinux](https://www.biglinux.com.br)) e **Tales A. Mendonça** ([BigCommunity](https://communitybig.org)).
- **Alfredo Kojima** ([Window Maker](https://www.windowmaker.org)) e **Philipp Kaeser** ([wlmaker](https://github.com/phkaeser/wlmaker)), sobre quem o Big WindowMaker é construído.

**Mantenedores:** Rafael Ruscher &lt;rruscher@gmail.com&gt; · Barnabé Di Kartola &lt;barnabedikartola@gmail.com&gt;

## 📄 Licença

[GPL-3.0-or-later](LICENSE). Os dados do catálogo derivados da Zorin Exec Guard App DB (GPL-2.0-or-later)
são redistribuídos sob a GPL-3.0-or-later, conforme a cláusula "ou posterior".

---

## English

**Big Trust Alt** identifies a downloaded program (a Windows `.exe`/`.msi`, a `.deb`, an `.rpm`, an
AppImage…) **without running it**. It then shows the best way to get that program on BigLinux:

- the repository package;
- the Flatpak;
- the AUR;
- the official Linux download;
- a clearly labelled functional alternative;
- or, if you choose it, Wine.

It is built with GTK4 + libadwaita and runs on Big WindowMaker X11 (Window Maker) and Wayland (wlmaker) and on other XDG desktops. It sends nothing over the network except AUR metadata queries. Its catalog has 358 verified entries.

To install, run `makepkg -si` in `pkgbuild/`. To use it, run `big-trust-alt FILE`, `big-trust-alt --analyze FILE --json` or `big-trust-alt --search NAME`. Contributions to the catalog are very welcome.
