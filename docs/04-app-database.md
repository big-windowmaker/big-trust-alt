# 04 — Catálogo (Big Trust Alt App DB)

`data/app-db/catalog/*.json`: **358 entradas** em 11 arquivos, esquema v1, todas conferidas em 12/11/2026.
265 entradas têm bloco `linux`; 247 vieram da base do Zorin (reescritas, com IDs conferidos).

| Tipo | Entradas |
|---|---|
| application | 304 |
| launcher (lojas e lançadores de jogos) | 17 |
| runtime (Java, .NET, VC++, DirectX…) | 13 |
| security (antivírus do Windows) | 11 |
| game | 7 |
| system (drivers, ISO do Windows…) | 6 |

**Esquema:**

- Validador: `src/big_trust_alt/database/schema.py`, que é a autoridade.
- Documentação: `data/schemas/catalog-v1.schema.json`.

| Campo | Para quê |
|---|---|
| `id`, `name`, `aliases`, `vendor`, `category`, `kind`, `platforms` | identidade |
| `match.filenames` | globs (`*`, `?`) sobre o **nome normalizado** (`"Firefox Setup 133.0.exe"` → `"firefox setup 133 0"`); no mínimo 3 letras fixas, no máximo 4 curingas, sem regex |
| `match.products` / `match.vendors` | ProductName/CompanyName do PE, Subject/Author do MSI, DisplayName do MSIX |
| `match.packages` | nome do pacote `.deb/.rpm/.pkg.tar` ou ID Flatpak |
| `match.formats` | restringe a quais formatos a entrada se aplica |
| `linux.packages` / `flatpak` / `desktop` / `website` / `instructions` / `steam` | o mesmo programa no Linux |
| `alternatives[]` | `successor`, `alternative`, `web`, `launcher`, com nota em en/pt_BR explicando a diferença |
| `windows.wine` | works, partial, unsupported, unknown, not-needed |
| `message` | casos especiais (antivírus, drivers, runtimes) |
| `verified`, `provenance` | data da última conferência e de onde vieram os dados |

**Como os dados foram conferidos:**

- Pacotes pelo `pacman -Sl` (repos do BigLinux/Manjaro) e pela lista completa do AUR, com a descrição de cada pacote do AUR lida.
- IDs Flatpak pela API do Flathub.
- `.desktop` pelas listas de arquivos dos repositórios.
- As 153 URLs respondem.

**Pontuação** (em `resolvers/matcher.py`):

| Evidência | Pontos |
|---|---|
| pacote igual | 80 |
| produto igual | 60 |
| glob do nome | 45 |
| fabricante | +20 |
| origem do download no site oficial | +10 |

A partir de 80 é **confirmado**; a partir de 40, **provável**. Dois candidatos a menos de 15 pontos um do outro são **ambíguos**, e aí o usuário escolhe.

**Colisões:** `tests/fixtures/catalog_samples.json` traz 422 nomes reais de instaladores, cada um precisa casar só com a sua entrada, e 93 nomes difíceis com o resultado esperado (chromedriver, mini_installer, setup.exe, WebView2, JRE × JDK…). O teste é `test_catalog_globs_do_not_collide`.

**Atualizar sem reinstalar:**

- Arquivos em `~/.local/share/big-trust-alt/catalog/*.json` sobrepõem as entradas pelo `id`.
- Um arquivo inválido é ignorado inteiro e o último catálogo válido continua valendo.
- A atualização pela rede, assinada, ainda não existe (ver o roteiro).

**Adicionar ou corrigir uma entrada:**

1. Edite o JSON do grupo.
2. Confira os pacotes e IDs nos repositórios reais.
3. Ponha a data de hoje em `verified`.
4. Rode `make check`.
5. Abra um PR. Use o botão "Informar identificação errada" do app para gerar os dados do arquivo.

**Pendente:**

- O anexo com cerca de 168 entradas citado na especificação não foi recebido.
- Alguns globs de instaladores que não puderam ser baixados são estimativas: Apple Music, Penpot, Proton Drive, Opera GX, Affinity, Norton, Kaspersky. Um glob errado simplesmente não casa.
