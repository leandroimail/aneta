# Validação da bibliometria Python

As entradas síncrona e assíncrona usam os registros OpenAlex da fase em execução. A opção histórica `bibliometry_generate_r_plots` controla as 34 saídas portadas. A opção `bibliometry_generate_py_charts` controla os relatórios Python preexistentes. O diretório `OUTPUTS/BIBLIOMETRY/<stage>/` contém o manifesto `bibliometry_artifacts.json`, com o resultado individual e a razão de cada figura omitida por insuficiência de dados.

## Referência utilizada

A comparação usou os mesmos 124 trabalhos da seleção final local nos dois ambientes. O script legado falhou antes de calcular as métricas com bibliometrix 5.5.0. Em uma cópia temporária, substituímos a chamada a `convert2df(df_works, dbsource="openalex", format="api")` pelo salvamento da lista OpenAlex original em RData e pela leitura desse arquivo com `dbsource="openalex_api"`. Isso produziu os workbooks e as 22 figuras de referência. A exportação HTML autocontida em R registrou ausência de Pandoc. O Python gerou os três HTML autocontidos. O [comparativo visual local](../../.data/BIBLIOMETRY/validacao-python/comparacao-graficos.pdf) reúne os pares de figuras.

| Saídas | Verificação e diferenças |
|---|---|
| Resumo e produção por autores | 124 trabalhos, 659 autores, 695 aparições, 3.766 referências distintas, 155 conceitos e 344 palavras-chave nos dois ambientes. Os 30 valores de produção absoluta e fracionada conferem ao arredondamento exibido pelo R. A ordem de nomes empatados pode variar. Python conserva os índices das três tabelas-resumo e exporta números sem o arredondamento de apresentação do R. |
| Artigos mais citados | Os 30 DOI do resumo e os 20 do gráfico coincidem. TC coincide exatamente. TC por ano e citação normalizada no top 20 diferem por menos de 0,000000000001. O gráfico inclui barras de TC e marcadores de citações anuais. |
| Citações locais | Os 20 DOI e os 20 valores de LCS coincidem. A rede histórica contém apenas referências identificadas no corpus e distribui os documentos pelo ano. |
| Palavras-chave por ano e crescimento | Os 20 termos e todas as contagens anuais na planilha coincidem. ID usa conceitos OpenAlex com escore mínimo de 0,5. Curvas acumuladas de termos e periódicos usam as frequências anuais. |
| Países, mapa e autoria | O país do primeiro autor correspondente, com fallback ao primeiro autor, define a atribuição de produção. Os EUA e Alemanha têm 21 e 12 artigos em ambos. A tabela Python omite países desconhecidos, usa os nomes da sua base geográfica e pode diferir na ordem de empates. O gráfico distingue colaboração nacional e internacional. |
| Produção e citações por ano | São exibidos todos os anos do intervalo. A média anual usa pelo menos um ano de exposição para evitar a divisão por zero do script de referência em artigos do ano corrente. |
| Redes e mapas temáticos | Layouts Python e R variam em coordenadas, rótulos, tamanhos e cores. As redes de termos e afiliações usam pesos por associação. O mapa temático usa Louvain, centralidade entre grupos e densidade intragrupo. |
| Estrutura conceitual e acoplamento | A análise de correspondências múltiplas usa indicadores de presença e ausência, SVD e agrupamento Ward. Sinais dos eixos, composição dos grupos, polígonos e seleção de rótulos podem variar entre implementações. O acoplamento usa referências compartilhadas, Walktrap e rankings de PageRank médio e impacto local normalizado. A igualdade de cada coordenada e comunidade permanece sem validação. |
| Interatividade e formatos | O Sankey e o treemap incorporam o Plotly e a nuvem usa SVG com frequência por termo. O PDF reúne as 22 figuras. O RDS é um data frame legível por R com as colunas bibliográficas usadas nas análises Python. O RDS legado inclui campos auxiliares adicionais de bibliometrix. |

O teste `tests/test_bibliometry_native.py` extrai os nomes de saída do script R e verifica todos em um corpus sintético, incluindo contagens locais, atribuição por país, leitura de RDS e remoção de figuras obsoletas. O teste das entradas por fase substitui a aquisição de metadados por dados locais e executa com PATH vazio. Uma falha total de aquisição preserva os resultados anteriores.
