# 05 — Identificação dos arquivos

Pelo **conteúdo** (assinaturas mágicas), nunca só pela extensão. Os leitores estão em `src/big_trust_alt/detectors/`.

| Formato | Como é reconhecido | O que é lido |
|---|---|---|
| `.exe` (PE) | `MZ` + `PE\0\0` | arquitetura (x86, x86_64, ARM64), GUI/console, VERSIONINFO (ProductName, CompanyName, FileDescription, versão, nome original), .NET (diretório CLR), assinatura Authenticode presente, manifesto (`requireAdministrator`), construtor do instalador (Inno, NSIS, InstallShield, WiX, Squirrel, 7-Zip SFX…) |
| `.msi` | OLE CFB `D0CF11E0` | SummaryInformation: Subject (produto), Author (fabricante), Template (plataforma) |
| `.msix/.appx` (+bundle) | ZIP com `AppxManifest.xml` | Identity, Publisher, DisplayName, arquitetura (XML com DTD recusado) |
| `.deb` | `!<arch>\ndebian-binary` | `control`: Package, Version, Architecture, Description |
| `.rpm` | `ED AB EE DB` | cabeçalho: Name, Version, Summary, Vendor, Arch |
| AppImage | ELF + `AI\x02` | arquitetura, `.upd_info` (dono/repositório de origem), assinatura presente |
| ELF (`.run/.bin`) | `\x7fELF` | classe, arquitetura, tipo |
| Scripts (`.sh/.run`) | texto + `#!` | interpretador, prévia (200 linhas), indícios (curl \| sh, sudo, rm -rf, dd, base64…), instalador makeself |
| `.bat/.cmd/.ps1` | texto + extensão | prévia; nunca tratados como compatíveis com Linux |
| `.jar` | ZIP com `META-INF/MANIFEST.MF` | Main-Class, título, fabricante, DLLs do Windows embutidas |
| `.pkg.tar.*` | tar com `.PKGINFO` | pkgname, pkgver, arch |
| `.tar.*`, `.zip` | magia gzip/xz/zstd/bzip2/zip | primeiros membros: install.sh, Makefile, .desktop, programas do Windows |
| `.flatpakref` / `.flatpak` | `[Flatpak Ref]` / extensão | Name, Url (avisa se o repositório não é o Flathub) |

**Avisos sobre o arquivo:**

- extensão que não bate com o conteúdo;
- programa com extensão de documento;
- extensão dupla;
- caracteres bidi/invisíveis no nome;
- arquitetura de outro processador;
- sem assinatura;
- danificado;
- vazio;
- link simbólico;
- gravável por outros;
- origem do download (xattr `user.xdg.origin.url`, gravado pelo Firefox e pelo Chromium).

**Medições** (este computador, cache quente, mediana de 5):

| Arquivo real | Tamanho | Detecção | Resolução | Com SHA-256 |
|---|---:|---:|---:|---:|
| ChromeSetup.exe | 13,3 MB | 22 ms | 0,8 ms | 31 ms |
| DiscordSetup.exe | 160,5 MB | 11 ms | 0,6 ms | 120 ms |
| npp.Installer.x64.exe | 7,0 MB | 2,2 ms | 0,9 ms | 6 ms |
| 7z2501-x64.msi | 2,0 MB | 0,4 ms | 0,6 ms | 2 ms |
| putty-64bit-0.85-installer.msi | 3,8 MB | 0,4 ms | 0,3 ms | 3 ms |

As 900 mutações aleatórias de cada formato (`test_mutations_never_crash`) nunca derrubam o leitor.
