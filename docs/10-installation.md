# 10 — Instalação e empacotamento

```bash
cd pkgbuild && makepkg -si           # da tag v0.1.0
BIG_TRUST_ALT_SOURCE="git+file://$PWD/..#branch=main" makepkg -si   # do clone local
```

O pacote roda `make build` (traduções), `make check` (catálogo + testes) e `make install DESTDIR=…`:

| Caminho | Conteúdo |
|---|---|
| `/usr/bin/big-trust-alt` | lançador (`python3 -m big_trust_alt` com `PYTHONPATH=/usr/share/big-trust-alt`) |
| `/usr/share/big-trust-alt/` | código, `app-db/catalog/*.json`, `schemas/` |
| `/usr/share/applications/io.github.big_windowmaker.BigTrustAlt.desktop` | tipos do Windows declarados, sem padrão gravado |
| `/usr/share/metainfo/…metainfo.xml` | AppStream (validado com `appstreamcli`) |
| `/usr/share/icons/hicolor/{scalable,symbolic}/apps/` | ícones |
| `/usr/share/locale/pt_BR/LC_MESSAGES/big-trust-alt.mo` | tradução |

**Validado em 12/11/2026:**

- `makepkg` sem erros; o `check()` passa (73 testes).
- `namcap` só aponta dependências implícitas (bash), além do `pacman` que é chamado em tempo de execução.
- Instalado com `pacman -U`.
- `big-trust-alt --version` e `--analyze` funcionam a partir de `/usr`.
- `gio mime application/x-msdownload` aponta para o app.
- `pacman -R` não deixa arquivos, limpa o cache MIME e o `.exe` volta a não ter padrão. Reinstalado em seguida.

**Arquivos do usuário** (criados só quando usados, nunca pelo pacote):

- `~/.config/big-trust-alt/settings.json`
- `~/.local/state/big-trust-alt/history.jsonl`
- `~/.local/share/big-trust-alt/catalog/` (sobreposição)
- `~/.config/mimeapps.list`, só pela opção de associação, que é reversível.

Sem caminhos fixos de usuário. O código roda igual instalado ou do clone (`PYTHONPATH=src`).
