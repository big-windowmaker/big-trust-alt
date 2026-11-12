# Contribuindo com o Big Trust Alt

## Catálogo (o mais útil)

1. Ache o grupo certo em `data/app-db/catalog/` (browsers, development, games…).
2. Siga o esquema em [docs/04-app-database.md](docs/04-app-database.md):
   - globs sobre o nome **normalizado** (`"Firefox Setup 133.0.exe"` → `"firefox setup 133 0"`);
   - pacotes e IDs Flatpak que **existem hoje** (`pacman -Si`, `flatpak remote-info flathub ID`, página do AUR);
   - alternativas com uma nota honesta da diferença, em en e pt_BR.
3. Acrescente nomes reais de instaladores em `tests/fixtures/catalog_samples.json`.
4. `make check`.

Nunca invente um pacote, uma versão ou um link.

## Código

- Python 3.12+, GTK4/libadwaita via PyGObject. Nada de dependência nova sem necessidade.
- **Detectores não executam, não extraem para o disco e não mudam permissões.**
- **O resolvedor não instala nem executa.**
- Comandos sempre como lista de argumentos; nunca `shell=True`.
- Nada de rede ou trabalho pesado na thread da interface.
- Todo texto visível passa por `_()`. Depois rode `python3 tools/update_po.py`, que atualiza o `.pot` e o `pt_BR.po` a partir de `tools/pt_BR.py`.
- `make check` e `ruff check src tests tools` antes do PR.

## Testar a interface

Sem mexer na sua sessão: um Xvfb com o Window Maker, ou o wlmaker aninhado, com HOME descartável
(veja [docs/09-tests.md](docs/09-tests.md)).

## Licença

Contribuições entram sob a GPL-3.0-or-later.
