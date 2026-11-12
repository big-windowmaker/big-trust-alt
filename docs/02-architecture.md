# 02 — Arquitetura

```
arquivo ─▶ detectors ─▶ FileReport ─▶ resolvers.matcher ─▶ candidatos + nível
                                          │
                     database.catalog ────┘
                                          ▼
                     providers (pacman, AUR, Flatpak, .desktop, ferramentas)
                                          ▼
                              resolvers.resolver ─▶ Analysis (opções + recomendada)
                                          ▼
                       ui (GTK4/libadwaita) · cli (texto/JSON)
                                          ▼
                       installers.runner (Pamac, Flatpak, big-pkg-installer, executar)
```

| Módulo | Responsabilidade | Não faz |
|---|---|---|
| `detectors/` | Lê o conteúdo: PE (version info, .NET, assinatura, instalador), MSI (SummaryInformation), ELF/AppImage, deb, rpm, pacote Arch, jar, msix/appx, scripts, flatpakref. | Não executa, não extrai para o disco, não muda permissões. |
| `security/fileinfo.py` | Abre sem seguir links trocados (`O_NOFOLLOW`), recusa FIFO/dispositivo, SHA-256, origem do download (xattr), nomes enganosos, `verify_unchanged`. | — |
| `database/` | Esquema v1 + validador, normalização, carga do catálogo (empacotado + sobreposição local validada). | — |
| `resolvers/matcher.py` | Pontua as evidências e decide confirmado/provável/ambíguo/desconhecido. | Não consulta pacotes. |
| `resolvers/resolver.py` | Monta as opções e a recomendada. | Não instala nem executa. |
| `providers/` | Visões somente leitura do sistema. | Não altera nada. |
| `installers/runner.py` | Executa a opção escolhida, verifica o resultado. | Nunca roda como root. |
| `ui/` | Janela, páginas, diálogos. | Sem lógica de negócio. |

Decisões:

- **Python + PyGObject, sem dependências novas**: tudo com a biblioteca padrão (o zstd vem do Python 3.14).
- **Catálogo em JSON** (um arquivo por grupo): fácil de revisar em PR e de validar, cerca de 360 entradas carregam em ~20 ms. SQLite não traria vantagem nesse tamanho.
- **Sem serviço em segundo plano**: a interceptação é pela associação MIME (XDG).
- **Threads de trabalho + `GLib.idle_add`**: análise, consultas e instalação nunca rodam na thread da interface.
