# Planejamento Descritivo — Modo Questões (Fuvest)

## 1. Visão Geral e Objetivos

O objetivo principal é criar uma nova seção no site chamada **"Questões"**. Esta seção permitirá que os usuários respondam a questões de provas anteriores da Fuvest de forma interativa e "gameficada". Para evitar custos altos e manter o projeto escalável, todo o processamento pesado (leitura de PDFs, uso de IA para explicações) será feito localmente em seu computador. O site em si apenas lerá arquivos de dados (JSONs) e imagens que já estarão prontos e versionados no GitHub.

**Principais Restrições (Decisões já tomadas):**
*   **Sem grandes mudanças na estrutura:** Manteremos o layout e a navegação existentes. A nova seção será apenas mais um item no menu.
*   **Tudo local:** O progresso do usuário será salvo no navegador (`localStorage`), sem necessidade de login.
*   **Foco em Múltipla Escolha:** Inicialmente, o sistema suportará apenas questões de múltipla escolha (A-E).
*   **Explicação Sempre:** Após responder (certo ou errado), o usuário sempre verá uma explicação detalhada da questão.
*   **Pipeline em Python:** Os scripts para processar os PDFs e gerar os dados serão em Python.
*   **Imagens Recortadas:** As imagens das questões serão salvas como arquivos de imagem (PNG) no projeto.

---

## 2. Estrutura do Projeto (O que será criado)

Para organizar o trabalho, criaremos novas pastas no projeto:

*   **`public/data/questions/`**: Onde ficarão os arquivos de dados (JSON) com as questões, um para cada ano de prova. O site lerá os dados daqui.
*   **`public/assets/questions/`**: Onde ficarão as imagens recortadas de cada questão, organizadas por ano e número da questão.
*   **`tools/questions/`**: Uma nova pasta na raiz do projeto que conterá todos os scripts Python e arquivos de suporte para o processamento dos PDFs. Esta pasta **não faz parte do site**, é apenas uma ferramenta para você gerar os dados.

---

## 3. As Fases do Desenvolvimento (Passo a Passo)

Vamos construir a funcionalidade em etapas, garantindo que cada parte funcione bem antes de passar para a próxima.

### Fase 1: Fundamentos dos Dados e Validação

**O que faremos:** Antes de escrever o código que processa os PDFs, vamos definir exatamente qual será a estrutura dos nossos arquivos de dados. Isso é como a "planta" da casa. Também criaremos um "validador", um script simples que verifica se um arquivo de dados está no formato correto, para evitar que dados quebrados entrem no site.

**Resultado esperado:** Uma estrutura de pastas clara e uma forma de garantir que nossos dados de questões sejam sempre consistentes e sem erros.

### Fase 2: Processamento dos PDFs (Extração)

**O que faremos:** Nesta fase, construiremos o coração do pipeline em Python. O script fará o seguinte:
1.  Pegará um arquivo `pXX.pdf` (a prova) e `gXX.pdf` (o gabarito).
2.  Converterá as páginas da prova em imagens.
3.  Enviará essas imagens para a IA (Gemini) para que ela "leia" a imagem, identifique onde cada questão está, extraia seu texto e alternativas.
4.  A IA também retornará as coordenadas para recortar a imagem da questão.
5.  O script usará essas coordenadas para salvar um arquivo de imagem (PNG) para cada questão.
6.  Por fim, ele lerá o gabarito e juntará a resposta correta com os dados da questão.

**Resultado esperado:** Ao final desta fase, teremos um script que, para um ano específico (ex: 2019), gera um arquivo `fuvest-2019.json` com todas as questões e uma pasta com todas as imagens recortadas daquela prova.

### Fase 3: Enriquecimento das Questões com IA

**O que faremos:** Com as questões já extraídas, vamos usar a IA novamente, mas desta vez para agir como um "professor". Para cada questão, o script pedirá à IA para gerar:
*   **Contexto Teórico:** O que o aluno precisa saber para resolver a questão.
*   **Passo a Passo:** A lógica da resolução.
*   **Análise dos Distratores:** Uma explicação do porquê cada uma das alternativas erradas está incorreta.
*   **Resumo Final:** Uma conclusão rápida.

**Resultado esperado:** O arquivo `fuvest-2019.json` será atualizado com explicações ricas e detalhadas para cada questão. O sistema terá um cache para não precisar pedir a mesma explicação duas vezes, economizando custos.

### Fase 4: Implementação no Site (Frontend)

**O que faremos:** Agora que temos os dados, vamos construir a interface no site.
1.  Adicionaremos o botão "Questões" no menu lateral.
2.  Criaremos uma nova página (componente `Questoes.jsx`) que irá carregar e exibir uma questão do nosso arquivo JSON.
3.  O usuário poderá selecionar uma alternativa e clicar em "Responder".
4.  O site mostrará se a resposta foi correta ou não e, em seguida, exibirá a explicação completa que geramos na Fase 3.
5.  O progresso do usuário (quais questões respondeu, acertos, erros) será salvo no navegador.

**Resultado esperado:** A funcionalidade estará completa do ponto de vista do usuário. Ele poderá entrar na nova seção, responder às questões e aprender com as explicações.

### Fase 5: Gamificação

**O que faremos:** Para tornar a experiência mais engajadora, adicionaremos elementos de jogo:
*   **Pontos de Experiência (XP):** O usuário ganhará pontos ao acertar questões.
*   **Sequência de Dias (Streak):** Um contador de dias consecutivos que o usuário praticou.
*   **Repetição Espaçada (SRS):** O sistema fará com que o usuário revise as questões que errou após alguns dias, para reforçar o aprendizado.

**Resultado esperado:** O usuário terá metas e um senso de progressão, incentivando o uso contínuo da ferramenta.

---

## 4. Próximos Passos

Com este plano descritivo, o próximo passo é eu começar a executar a **Fase 1**, criando as pastas necessárias e a estrutura de validação. A partir daí, avançaremos fase por fase, sempre mantendo você informado do progresso. Este formato evita problemas com o terminal e foca no que realmente será construído.
