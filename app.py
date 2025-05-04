import os
import json
import requests
import re
import time
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from wordcloud import WordCloud

# ========== CONFIGURAÇÃO ==========
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

# ========== DEFINIÇÃO DO PROBLEMA ==========
"""
ANÁLISE DE SENTIMENTOS EM OBRAS DE AUTORES CLÁSSICOS

OBJETIVOS:
1. Identificar padrões emocionais característicos de cada autor
2. Comparar o espectro emocional entre diferentes estilos literários
3. Gerar insights sobre como cada autor trabalha as emoções em suas obras
"""

# ========== FUNÇÕES AUXILIARES ==========
def corrigir_texto(texto):
    """Remove espaços extras e caracteres especiais"""
    return re.sub(r'\s+', ' ', texto).strip()

def chamar_gemini(prompt, max_retries=3):
    """Função genérica para chamar a API do Gemini com tratamento de erros"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    for attempt in range(max_retries):
        try:
            response = requests.post(GEMINI_API_URL, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            elif response.status_code == 429:
                retry_delay = int(response.json().get('error', {}).get('details', [{}])[-1].get('retryDelay', '60s').replace('s', ''))
                print(f"Rate limit atingido. Aguardando {retry_delay}s...")
                time.sleep(retry_delay)
                continue
                
            else:
                print(f"Erro na API: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Erro na tentativa {attempt + 1}: {str(e)}")
            time.sleep(5)
    
    return None

# ========== FUNÇÕES DE SCRAPING ==========
def extrair_metadados_livro(livro_div, autor):
    """Extrai metadados do livro da nova estrutura HTML"""
    try:
        # Título
        titulo_tag = livro_div.find('h2', class_='has-text-align-center') or livro_div.find('h3')
        titulo = corrigir_texto(titulo_tag.get_text()) if titulo_tag else f"Livro de {autor}"
        
        # Link de download
        download_div = livro_div.find('div', class_='btn-descargar')
        link_tag = download_div.find('a') if download_div else None
        link_download = link_tag['href'] if link_tag else None
        
        # Descrição
        descricao_div = livro_div.find('div', class_='descripcion')
        descricao = ' '.join(p.get_text() for p in descricao_div.find_all('p')) if descricao_div else ""
        
        # Imagem da capa
        img_tag = livro_div.find('img')
        imagem_url = (img_tag.get('data-src') or img_tag.get('src')) if img_tag else None
        if imagem_url and imagem_url.startswith("/"):
            imagem_url = "https://www.infolivros.org" + imagem_url
        
        return {
            'autor': autor,
            'titulo': titulo,
            'descricao': descricao,
            'link_download': link_download,
            'imagem_capa': imagem_url,
        }
        
    except Exception as e:
        print(f"Erro ao extrair livro: {str(e)}")
        return None

def scrape_autor(url, autor, max_livros=3):
    """Coleta livros de um autor específico"""
    try:
        print(f"\n🔍 Coletando obras de: {autor}")
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        livros = []
        for livro_div in soup.find_all('div', class_='content_libro_autor')[:max_livros]:
            livro_info = extrair_metadados_livro(livro_div, autor)
            if livro_info:
                livros.append(livro_info)
        
        return livros
        
    except Exception as e:
        print(f"Erro ao processar {autor}: {str(e)}")
        return []

# ========== ANÁLISE DE SENTIMENTOS ==========
def analisar_sentimentos(livros):
    """Analisa sentimentos usando Gemini e gera insights"""
    for livro in livros:
        if not livro.get('sentimentos'):
            prompt = f"""
            Analise o livro abaixo e identifique os 3 principais sentimentos que ele transmite.
            Considere o estilo característico do autor {livro['autor']}.
            Responda APENAS com uma lista JSON contendo exatamente 3 sentimentos em português.
            
            Exemplo válido: ["melancolia", "angústia", "solidão"]
            
            Título: {livro['titulo']}
            Autor: {livro['autor']}
            Descrição: {livro['descricao'][:1000]}... [truncado]
            """
            
            sentimentos_json = chamar_gemini(prompt) or "[]"
            try:
                livro['sentimentos'] = json.loads(sentimentos_json.replace("```json", "").replace("```", "").strip())[:3]
            except:
                livro['sentimentos'] = []
            
            time.sleep(1.5)  # Intervalo entre chamadas à API
    
    return livros

# ========== VISUALIZAÇÃO E INSIGHTS ==========
def gerar_visualizacoes(livros):
    """Gera visualizações avançadas e insights"""
    if not livros:
        print("Nenhum dado para visualizar")
        return
    
    # Preparar dados
    dados_autores = {}
    todos_sentimentos = []
    
    for livro in livros:
        autor = livro['autor']
        if autor not in dados_autores:
            dados_autores[autor] = {
                'sentimentos': [],
                'obras': []
            }
        
        dados_autores[autor]['sentimentos'].extend(livro['sentimentos'])
        dados_autores[autor]['obras'].append(livro['titulo'])
        todos_sentimentos.extend(livro['sentimentos'])
    
    # 1. Heatmap de Frequência de Sentimentos por Autor
    plt.figure(figsize=(14, 8))
    sentimentos_unicos = sorted(list({sent for autor in dados_autores for sent in dados_autores[autor]['sentimentos']}))
    autores = sorted(dados_autores.keys())
    
    dados_heatmap = []
    for autor in autores:
        contador = Counter(dados_autores[autor]['sentimentos'])
        linha = [contador.get(sent, 0) for sent in sentimentos_unicos]
        dados_heatmap.append(linha)
    
    sns.heatmap(dados_heatmap, annot=True, fmt='d', cmap='YlOrRd',
                xticklabels=sentimentos_unicos, yticklabels=autores)
    plt.title('Frequência de Sentimentos por Autor', pad=20)
    plt.xlabel('Sentimentos')
    plt.ylabel('Autores')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig('heatmap_sentimentos.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. Radar Plot de Perfil Emocional
    plt.figure(figsize=(10, 10))
    ax = plt.subplot(111, polar=True)
    
    for autor in autores:
        contador = Counter(dados_autores[autor]['sentimentos'])
        valores = [contador.get(sent, 0) for sent in sentimentos_unicos]
        valores += valores[:1]  # Fechar o radar
        
        angulos = [n / len(sentimentos_unicos) * 2 * 3.14159 for n in range(len(sentimentos_unicos))]
        angulos += angulos[:1]
        
        ax.plot(angulos, valores, linewidth=1, linestyle='solid', label=autor)
        ax.fill(angulos, valores, alpha=0.1)
    
    ax.set_theta_offset(3.14159 / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids([a * 180/3.14159 for a in angulos[:-1]], sentimentos_unicos)
    plt.title('Perfil Emocional Comparativo', pad=20)
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    plt.savefig('radar_sentimentos.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. Nuvens de palavras individuais por autor
    for autor in dados_autores:
        if dados_autores[autor]['sentimentos']:
            wordcloud = WordCloud(width=800, height=400, 
                                background_color='white',
                                colormap='viridis').generate(' '.join(dados_autores[autor]['sentimentos']))
            
            plt.figure(figsize=(10, 5))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis("off")
            plt.title(f"Sentimentos em obras de {autor}", pad=20)
            plt.savefig(f'nuvem_{autor.lower().replace(" ", "_")}.png', dpi=300, bbox_inches='tight')
            plt.close()
    
    # 4. Nuvem de palavras geral (todos autores)
    if todos_sentimentos:
        wordcloud = WordCloud(width=1200, height=600,
                            background_color='white',
                            colormap='plasma').generate(' '.join(todos_sentimentos))
        
        plt.figure(figsize=(15, 8))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis("off")
        plt.title("Sentimentos em Obras Clássicas (Todos Autores)", pad=20)
        plt.savefig('nuvem_geral.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    # Gerar insights textuais
    insights = []
    for autor in autores:
        sentimentos_principais = Counter(dados_autores[autor]['sentimentos']).most_common(3)
        
        insight = f"""
        AUTOR: {autor.upper()}
        Obras analisadas: {', '.join(dados_autores[autor]['obras'])}
        Top 3 sentimentos:
        1. {sentimentos_principais[0][0]} ({sentimentos_principais[0][1]} ocorrências)
        2. {sentimentos_principais[1][0]} ({sentimentos_principais[1][1]} ocorrências)
        3. {sentimentos_principais[2][0]} ({sentimentos_principais[2][1]} ocorrências)
        """
        insights.append(insight)
    
    # Insight comparativo geral
    sentimentos_gerais = Counter(todos_sentimentos).most_common(5)
    insights.append(f"""
    VISÃO GERAL:
    Sentimentos mais frequentes em todas as obras:
    1. {sentimentos_gerais[0][0]} ({sentimentos_gerais[0][1]} ocorrências)
    2. {sentimentos_gerais[1][0]} ({sentimentos_gerais[1][1]} ocorrências)
    3. {sentimentos_gerais[2][0]} ({sentimentos_gerais[2][1]} ocorrências)
    4. {sentimentos_gerais[3][0]} ({sentimentos_gerais[3][1]} ocorrências)
    5. {sentimentos_gerais[4][0]} ({sentimentos_gerais[4][1]} ocorrências)
    """)
    
    with open("insights_autores.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(insights))
    
    print("\n✅ Visualizações salvas:")
    print("- heatmap_sentimentos.png (Heatmap de frequência)")
    print("- radar_sentimentos.png (Perfil comparativo)")
    print("- nuvem_[autor].png (Nuvens de palavras por autor)")
    print("- nuvem_geral.png (Nuvem de todos os sentimentos)")
    print("- insights_autores.txt (Análise textual)")

# ========== EXECUÇÃO PRINCIPAL ==========
def main():
    autores = {
        "William Shakespeare": "https://www.infolivros.org/autores/classicos/livros-william-shakespeare/",
        "Irmãos Grimm": "https://www.infolivros.org/autores/classicos/livros-irmaos-grimm/",
        "H.P. Lovecraft": "https://www.infolivros.org/autores/classicos/livros-hp-lovecraft/",
        "Edgar Allan Poe": "https://www.infolivros.org/autores/classicos/livros-edgar-allan-poe/",
        "Agatha Christie": "https://www.infolivros.org/autores/classicos/livros-agatha-christie/"
    }
    
    todos_livros = []
    
    # Coletar e analisar livros
    for autor, url in autores.items():
        livros_autor = scrape_autor(url, autor)
        if livros_autor:
            livros_analisados = analisar_sentimentos(livros_autor)
            todos_livros.extend(livros_analisados)
            time.sleep(3)  # Intervalo entre autores
    
    # Salvar resultados
    with open("livros_analisados.json", "w", encoding="utf-8") as f:
        json.dump({"livros": todos_livros}, f, ensure_ascii=False, indent=2)
    
    # Gerar visualizações e insights
    gerar_visualizacoes(todos_livros)
    
    print("\n✅ Análise concluída com sucesso!")
    print(f"📊 Total de livros analisados: {len(todos_livros)}")
    print(f"📄 Resultados completos em 'livros_analisados.json'")

if __name__ == "__main__":
    main()