# 03 — Modelo de ameaças e segurança

**O que protegemos:** o usuário que abre um arquivo baixado sem saber o que ele é.
**Fora do escopo:** detectar malware. O Big Trust Alt **não é antivírus** e uma identificação não significa "seguro".

| Ameaça | Defesa | Teste |
|---|---|---|
| Executar algo só por abrir/analisar | A análise só lê (bytes limitados); executar exige o diálogo de confirmação, com "Cancelar" como padrão. | `test_script_hints_and_no_execution` |
| Extensão falsa, extensão dupla, RTLO (`fatura‮fdp.exe`) | Formato pelo conteúdo; avisos `disguised-executable`, `double-extension`, `deceptive-name`; o nome é mostrado com os caracteres invisíveis à vista. | `test_disguised_*`, `test_rtlo_name` |
| Injeção de comando pelo nome | Comandos sempre como lista de argumentos, sem shell. | `test_malicious_name_stays_one_argument`, `test_wine_command_is_an_argument_list` |
| Troca do arquivo entre a análise e a execução (TOCTOU) | Dispositivo, inode, tamanho, mtime e SHA-256 conferidos de novo antes de executar. | `test_changed_file_is_refused`, `test_replaced_file_*` |
| Link simbólico / FIFO / dispositivo | `realpath` + `O_NOFOLLOW` + `O_NONBLOCK`; só arquivo regular. | `test_errors`, `test_symlink_recorded` |
| Arquivo malformado (DoS no parser) | Todos os offsets conferidos; limites de leitura, de cadeia de setores, de descompressão (32 MiB) e de membros; XML com DTD recusado. | `test_mutations_never_crash` (900 mutações) |
| Permissão de execução sem consentimento | `chmod u+x` só com a caixa marcada no diálogo. | `test_exec_bit_needs_consent` |
| Privilégios | O programa nunca roda como root. Pamac e Flatpak pedem o Polkit pelos próprios mecanismos. | — |
| AUR | Marcado como pacote da comunidade, com aviso; desatualizado ou órfão vira "Experimental" e nunca é recomendado. O Pamac mostra os arquivos de compilação antes. | `test_prefer_flatpak_and_hide_aur` |
| Wine | Avisado em todo lugar: **não é sandbox**. Nunca recomendado. | — |
| Privacidade | Nada é enviado: sem telemetria, sem envio de arquivos. O histórico guarda só o nome do arquivo (0600). O relatório de identificação errada é copiado para a área de transferência, sem pastas. | `test_history_keeps_names_not_paths` |
| Catálogo adulterado | Validação de esquema; globs sem regex (sem ReDoS); sobreposição inválida é ignorada inteira. | `test_schema_rejects`, `test_overlay_invalid_is_ignored` |

**Limites conhecidos:**

- A assinatura Authenticode é detectada, mas **não verificada**, e é mostrada assim.
- Entre a última verificação e o `exec` ainda existe uma janela de microssegundos. Fechá-la exigiria copiar o arquivo, o que quebra instaladores que leem arquivos vizinhos.
