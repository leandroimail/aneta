# Revisão de armazenamento, bibliometria e integridade

## Medições

No diretório da revisão analisada, a contagem por dispositivo e inode encontrou 318.554.112 bytes alocados em OUTPUTS, 221.265.920 em PDFs e 19.140.608 em .bibs. A comparação SHA-256 encontrou 225.207.093 bytes lógicos repetidos. Destes, 211.698.684 correspondem aos 121 PDFs da entrega que também aparecem na pasta de aquisição. A medição por inode não distingue blocos compartilhados por clones APFS.

Em diretórios temporários, repetimos duas revisões com os mesmos 12 registros do JSON OpenAlex local. O backend anterior gravou duas tabelas Lance com o fluxo de merge e otimização por registro. As duas tabelas ocuparam 4.448.256 bytes alocados. O banco compartilhado novo e os dois índices de versões ocuparam 102.400 bytes, redução de 97,7% nessa amostra. O resultado varia com o corpus e o sistema de arquivos.

## Revisão adversarial do plano e correções

| Achado | Decisão implementada | Verificação |
| --- | --- | --- |
| A seleção recriava toda a pasta OUTPUTS | Criar o diretório de forma idempotente e gravar os arquivos da seleção individualmente | Sentinela de outra etapa preservada |
| A exportação apagava o destino e podia copiar seus próprios arquivos | Preparar a entrega ao lado do destino, validar sobreposições e inventário, preservar entrega legada reconhecida | Testes de exportação, reexportação e proteção de conteúdo |
| Uma importação antiga podia sobrescrever a versão atual | Manter versões por revisão e importar histórico sem promover o registro sobre uma versão existente | Casos de importação e retomada |
| Chaves lowercase de cache e nomes de PDF têm requisitos diferentes | Centralizar ambos preservando a grafia dos arquivos em disco | Extração, relatório, exportação e download |
| Resultado parcial podia passar por uma busca completa | Validar respostas e publicar a busca concluída a partir de área temporária fora dos BibTeX lidos pela seleção | Seis provedores com HTTP simulado, repetição offline e falha parcial |
| Parsers idênticos de triagem divergiriam com manutenção separada | Compartilhar o parser das entradas síncrona e assíncrona, preservando o contrato específico da consolidação | Suíte de triagem e consolidação |

O levantamento geral também identificou duplicação entre os enriquecedores síncrono e assíncrono, conversores Scopus legados e chamadas HTTP sem timeout. As rotas de busca ativas receberam limites de espera. A consolidação dos enriquecedores exige testes de equivalência específicos dos provedores. Os totais de alertas de análise estática incluem código legado e precisam de triagem individual.

Na revisão adversarial final, os revisores reproduziram uma regressão ao importar PDFs antigos, ambiguidade no JSON OpenAlex da entrega, perda de resultados após falha de aquisição e dois problemas em dados bibliográficos de entrada. Os testes agora verificam que a versão compartilhada atual sobrevive à retomada, o JSON genérico da entrega corresponde à fase final, os resultados sobrevivem a falhas de aquisição, os títulos iniciados por sinal de igual são gravados como texto no Excel e as afiliações nulas são aceitas. A validação da CLI usou os dois estágios em um diretório temporário, com 12 registros na entrada pós-abstract e oito na final. Os resultados por gráfico e planilha estão na [matriz de paridade](paridade-bibliometria.md).
