# -*- coding: utf-8 -*-
"""
================================================================================
CODE UNIFIER - UNIFICADOR INTELIGENTE DE CÓDIGO-FONTE
================================================================================

DESCRIÇÃO:
    Ferramenta profissional para consolidação e documentação de código-fonte.
    Varre recursivamente diretórios, agrega arquivos de programação em documentos
    Markdown estruturados com índice navegável, metadados e divisão inteligente
    por tamanho.

CARACTERÍSTICAS PRINCIPAIS:
    1. Varredura recursiva com filtros por extensão
    2. Ignorar diretórios de sistema/controle de versão (configurável)
    3. Detecção automática de encoding (UTF-8, Latin-1, etc.)
    4. Geração de sumário clicável com âncoras HTML
    5. Divisão balanceada em múltiplos arquivos por tamanho
    6. Inclusão de metadados (SHA-1, linhas, tamanho, data)
    7. Formatação de código com syntax highlighting via Markdown
    8. Opções de visualização (recolhível, separadores, quebras)
    9. Interface gráfica intuitiva (Tkinter)

ALGORITMO DE DIVISÃO:
    Utiliza heurística gulosa para distribuir arquivos em N grupos balanceados
    por tamanho total, garantindo que partes grandes fiquem distribuídas
    uniformemente.

USO TÍPICO:
    - Documentação de projetos para entrega
    - Preparação de código para análise por LLMs/AI
    - Criação de snapshots para revisão de código
    - Geração de artefatos para auditoria
    - Backup estruturado de código-fonte

AUTOR: [Seu Nome/Organização]
VERSÃO: 2.0.0
LICENÇA: MIT
================================================================================
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import datetime
from pathlib import Path
import hashlib
from typing import Set, List, Optional

# ============================================================================
# CONFIGURAÇÕES BASE DO SISTEMA
# ============================================================================

# Mapeamento de extensões para linguagens Markdown (syntax highlighting)
LANG_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".js": "javascript",
    ".ts": "typescript",
    ".json": "json",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sql": "sql",
    ".ini": "ini",
    ".txt": ""
}

# Extensões permitidas por padrão (ordenadas alfabeticamente)
DEFAULT_EXTS = sorted(LANG_BY_EXT.keys())

# Diretórios a serem ignorados automaticamente (sistema/controle versão)
DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules",
    "venv", ".venv", "env", ".env", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".idea", ".vscode", ".DS_Store"
}

# Limite máximo de bytes por arquivo (evita carregar arquivos muito grandes)
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB

# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================


def read_text_safely(path: Path) -> str:
    """
    Lê um arquivo de texto com detecção automática de encoding.
    
    ESTRATÉGIA:
        1. Tenta leituras estritas com encodings comuns (UTF-8-sig, UTF-8, Latin-1)
        2. Fallback para decodificação tolerante se todas falharem
        3. Normaliza terminadores de linha para \n
    
    Args:
        path: Caminho do arquivo a ser lido
        
    Returns:
        Conteúdo do arquivo como string unificada
    """
    # Tentativa 1: Leituras estritas com encodings prioritários
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with path.open("r", encoding=enc, errors="strict") as f:
                txt = f.read()
            # Normalização de terminadores de linha
            return txt.replace("\r\n", "\n").replace("\r", "\n")
        except Exception:
            continue
    
    # Tentativa 2: Fallback binário + decodificação tolerante
    data = path.read_bytes()
    try:
        txt = data.decode("utf-8", errors="replace")
    except Exception:
        txt = data.decode("latin-1", errors="replace")
    
    return txt.replace("\r\n", "\n").replace("\r", "\n")


def guess_lang(path: Path) -> str:
    """
    Determina a linguagem de programação baseada na extensão do arquivo.
    
    Args:
        path: Caminho do arquivo
        
    Returns:
        String identificadora da linguagem para Markdown ou string vazia
    """
    return LANG_BY_EXT.get(path.suffix.lower(), "")


def sha1_of_text(text: str) -> str:
    """
    Calcula hash SHA-1 do conteúdo textual.
    
    Args:
        text: Conteúdo textual a ser hasheado
        
    Returns:
        String hexadecimal de 40 caracteres representando o hash SHA-1
    """
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def human_size(num_bytes: int) -> str:
    """
    Converte bytes para formato humano-legível (KB, MB, GB).
    
    Args:
        num_bytes: Quantidade de bytes
        
    Returns:
        String formatada com unidade apropriada
    """
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    
    for u in units:
        if size < 1024 or u == units[-1]:
            # Formatação diferenciada para bytes vs outras unidades
            return f"{size:.0f} {u}" if u == "B" else f"{size:.2f} {u}"
        size /= 1024.0
    
    return f"{num_bytes} B"  # Fallback


def anchor_from_rel(rel: str) -> str:
    """
    Gera um identificador HTML seguro a partir de um caminho relativo.
    
    PROCESSO:
        1. Converte para minúsculas
        2. Substitui espaços por hífens
        3. Remove caracteres especiais que podem quebrar URLs HTML
        
    Args:
        rel: Caminho relativo do arquivo
        
    Returns:
        String segura para uso como âncora HTML
    """
    a = rel.lower().replace(" ", "-")
    
    # Remove caracteres problemáticos para URLs/anchor links
    for ch in "()[]{}!@#$%^&*+=?;:,<>\\|\"'":
        a = a.replace(ch, "")
    
    return a


def build_section(
    path: Path,
    content: str,
    index: int,
    total: int,
    root: Path,
    strong_sep: bool = True,
    collapsible: bool = False,
    include_hash: bool = True,
    page_break: bool = False
) -> str:
    """
    Constrói uma seção Markdown completa para um arquivo.
    
    ESTRUTURA DA SEÇÃO:
        1. Separador visual (opcional)
        2. Âncora HTML para navegação
        3. Cabeçalho com metadados
        4. Bloco de código formatado
        5. Controles de colapso (opcional)
        6. Quebra de página (opcional)
    
    Args:
        path: Caminho absoluto do arquivo
        content: Conteúdo textual do arquivo
        index: Índice atual (para numeração)
        total: Total de arquivos na parte atual
        root: Diretório raiz do projeto
        strong_sep: Usar separador forte (───) em vez de simples (---)
        collapsible: Envolver código em tags <details> para recolhimento
        include_hash: Incluir hash SHA-1 do conteúdo
        page_break: Adicionar comentário de quebra de página para impressão
        
    Returns:
        String Markdown formatada da seção
    """
    # Extração de metadados
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = str(path)
    
    lang = guess_lang(path)
    
    try:
        mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_bytes = path.stat().st_size
    except OSError:
        mtime = "Erro ao ler data"
        size_bytes = 0
    
    size_h = human_size(size_bytes)
    n_lines = content.count("\n") + (0 if content.endswith("\n") else 1)
    file_hash = sha1_of_text(content) if include_hash else None
    anchor = anchor_from_rel(rel)
    
    # Configuração do separador
    sep = "\n" + "─" * 88 + "\n" if strong_sep else "\n---\n"
    
    # Construção do cabeçalho
    header_lines = [
        sep,
        f'<a id="{anchor}"></a>',
        f"## [{index}/{total}] {rel}",
        "",
        f"**Tamanho:** {size_h} | **Linhas:** {n_lines} | **Mod.:** {mtime}" +
        (f" | **SHA-1:** `{file_hash}`" if file_hash else ""),
        ""
    ]
    
    # Bloco de código com syntax highlighting
    fence_open = f"```{lang}".rstrip()
    code_block = f"{fence_open}\n{content.rstrip()}\n```\n"
    
    # Montagem final com opções
    if collapsible:
        section = "\n".join(header_lines) + \
                  f"<details>\n<summary>ver código</summary>\n\n" + \
                  code_block + "\n</details>\n"
    else:
        section = "\n".join(header_lines) + "\n" + code_block
    
    # Adição de quebra de página se necessário
    if page_break:
        section += "\n<!-- PAGE BREAK -->\n"
    
    return section


def scan_files(
    root: Path,
    allowed_exts: Set[str],
    include_hidden: bool = False,
    ignore_dirs_extra: Optional[str] = None
) -> List[Path]:
    """
    Varre recursivamente diretório e coleta arquivos válidos.
    
    ALGORITMO:
        1. Percorre árvore de diretórios com os.walk()
        2. Filtra diretórios ignorados (sistema + customizados)
        3. Filtra por extensões permitidas
        4. Verifica tamanho máximo
        5. Ordena resultados por extensão e nome
    
    Args:
        root: Diretório raiz para iniciar a varredura
        allowed_exts: Conjunto de extensões permitidas
        include_hidden: Incluir arquivos/diretórios ocultos (iniciando com .)
        ignore_dirs_extra: String com diretórios adicionais a ignorar
                           (separados por vírgula ou ponto-e-vírgula)
        
    Returns:
        Lista ordenada de Paths para arquivos válidos
    """
    # Configuração de diretórios a ignorar
    ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    if ignore_dirs_extra:
        # Processa string com separadores múltiplos
        tokens = [p.strip() for p in ignore_dirs_extra.replace(";", ",").split(",") if p.strip()]
        for token in tokens:
            if token:
                ignore_dirs.add(token)
    
    files: List[Path] = []
    
    # Varredura recursiva
    for dirpath, dirnames, filenames in os.walk(root):
        # Filtra subdiretórios antes de descer na recursão
        dirnames[:] = [d for d in dirnames
                       if d not in ignore_dirs and 
                       (include_hidden or not d.startswith("."))]
        
        # Pula diretórios ocultos se configurado
        if not include_hidden and any(part.startswith(".") for part in Path(dirpath).parts):
            continue
        
        # Processa arquivos no diretório atual
        for fname in filenames:
            p = Path(dirpath) / fname
            
            # Filtro de arquivos ocultos
            if not include_hidden and fname.startswith("."):
                continue
            
            # Filtro por extensão
            if p.suffix.lower() not in allowed_exts:
                continue
            
            # Verificação de tamanho máximo
            try:
                size = p.stat().st_size
                if size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue  # Ignora arquivos inacessíveis
            
            files.append(p)
    
    # Ordenação: primeiro por extensão, depois por nome (case-insensitive)
    files = sorted(files, key=lambda f: (f.suffix.lower(), f.as_posix().lower()))
    
    return files


# ============================================================================
# ALGORITMO DE DIVISÃO BALANCEADA
# ============================================================================


def distribute_by_size(files: List[Path], k: int) -> List[List[Path]]:
    """
    Distribui arquivos em k grupos balanceados por tamanho total.
    
    HEURÍSTICA GULOSA:
        1. Ordena arquivos por tamanho (decrescente)
        2. Para cada arquivo, atribui ao grupo com menor tamanho acumulado
        3. Mantém balanço aproximado entre grupos
    
    Complexidade: O(n log n) para ordenação + O(n*k) para distribuição
    
    Args:
        files: Lista de arquivos a serem distribuídos
        k: Número de grupos desejados
        
    Returns:
        Lista de k listas com Paths distribuídos
    """
    # Caso trivial: um grupo único
    if k <= 1:
        return [files]
    
    # Pré-calcula tamanhos (evita múltiplas chamadas stat())
    sizes = {p: p.stat().st_size for p in files}
    
    # Ordenação decrescente por tamanho (largest-first)
    order = sorted(files, key=lambda p: sizes[p], reverse=True)
    
    # Inicializa grupos vazios e acumuladores de tamanho
    buckets: List[List[Path]] = [[] for _ in range(k)]
    totals = [0] * k
    
    # Distribuição gulosa
    for p in order:
        # Encontra grupo com menor tamanho acumulado
        idx = min(range(k), key=lambda i: totals[i])
        buckets[idx].append(p)
        totals[idx] += sizes[p]
    
    return buckets


def write_unified_md(
    destino: Path,
    root: Path,
    files: List[Path],
    titulo: str,
    strong_sep: bool,
    collapsible: bool,
    include_hash: bool,
    page_break: bool,
    part_idx: int = 1,
    part_total: int = 1
) -> None:
    """
    Gera arquivo Markdown unificado com todos os arquivos processados.
    
    ESTRUTURA DO DOCUMENTO:
        1. Título principal (com partição se aplicável)
        2. Metadados do projeto (raiz, data, contagem)
        3. Índice navegável com links âncora
        4. Separador principal
        5. Seções individuais para cada arquivo
    
    Args:
        destino: Caminho de saída para o arquivo Markdown
        root: Diretório raiz do projeto
        files: Lista de arquivos a incluir nesta parte
        titulo: Título principal do documento
        strong_sep: Usar separadores fortes
        collapsible: Habilitar seções recolhíveis
        include_hash: Incluir hashes SHA-1
        page_break: Adicionar quebras de página
        part_idx: Índice da parte atual (1-based)
        part_total: Total de partes geradas
    """
    # Cabeçalho com metadados
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = []
    
    # Título adaptado para multi-parte
    if part_total == 1:
        title_full = titulo
    else:
        title_full = f"{titulo} — Parte {part_idx}/{part_total}"
    
    lines.append(f"# {title_full}\n")
    
    # Linhas de metadados
    lines.append(f"Raiz: `{root.as_posix()}`  ")
    lines.append(f"Gerado em: **{now}**  ")
    lines.append(f"Arquivos nesta parte: **{len(files)}**\n")
    
    # Índice navegável
    lines.append("## Índice\n")
    for i, p in enumerate(files, 1):
        try:
            rel = p.relative_to(root).as_posix()
        except ValueError:
            rel = str(p)
        anc = anchor_from_rel(rel)
        lines.append(f"- {i}. [{rel}](#{anc})")
    lines.append("\n---\n")
    
    # Processamento individual de cada arquivo
    total = len(files)
    for i, p in enumerate(files, 1):
        try:
            content = read_text_safely(p)
        except Exception as e:
            content = f"<<ERRO AO LER: {e}>>"
        
        # Construção da seção individual
        section = build_section(
            p, content, i, total, root,
            strong_sep=strong_sep,
            collapsible=collapsible,
            include_hash=include_hash,
            page_break=page_break
        )
        lines.append(section)
    
    # Escrita final com encoding UTF-8
    destino.write_text("\n".join(lines), encoding="utf-8")


# ============================================================================
# INTERFACE GRÁFICA - APLICAÇÃO PRINCIPAL
# ============================================================================


class CodeUnifierPro(tk.Tk):
    """
    Classe principal da aplicação gráfica Code Unifier Pro.
    
    GERENCIAMENTO DE LAYOUT:
        Utiliza sistema de grid/flow com Tkinter/ttk para interface responsiva
        e organizada em seções lógicas.
    """
    
    def __init__(self):
        """Inicializa a aplicação com configurações de janela e widgets."""
        super().__init__()
        
        # Configurações da janela principal
        self.title("Code Unifier Pro - Unificador Inteligente de Código")
        self.geometry("980x700")
        self.minsize(800, 600)
        
        # Variáveis de estado (CRIAR ANTES de qualquer método que as use)
        self.outdir_var = tk.StringVar(value="")
        self.var_hidden = tk.BooleanVar(value=False)
        self.var_strong = tk.BooleanVar(value=True)
        self.var_collapse = tk.BooleanVar(value=False)
        self.var_hash = tk.BooleanVar(value=True)
        self.var_pagebreak = tk.BooleanVar(value=False)
        
        # Frame principal com padding
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        
        # Configuração de todas as seções da interface
        self._setup_root_section(frm)
        self._setup_extensions_section(frm)
        self._setup_ignore_section(frm)
        self._setup_options_section(frm)
        self._setup_title_section(frm)
        self._setup_split_section(frm)
        self._setup_output_section(frm)
        self._setup_action_section(frm)
        self._setup_list_section(frm)
        self._setup_footer(frm)
    
    # ========================================================================
    # SEÇÕES DA INTERFACE - MÉTODOS DE CONFIGURAÇÃO
    # ========================================================================
    
    def _setup_root_section(self, parent: ttk.Frame) -> None:
        """Configura seção de seleção de pasta raiz."""
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        
        ttk.Label(row, text="Pasta raiz:").pack(side="left")
        
        self.ent_root = ttk.Entry(row)
        self.ent_root.pack(side="left", fill="x", expand=True, padx=6)
        
        ttk.Button(
            row,
            text="Escolher…",
            command=self.choose_root
        ).pack(side="left")
    
    def _setup_extensions_section(self, parent: ttk.Frame) -> None:
        """Configura seção de extensões de arquivo."""
        row2 = ttk.Frame(parent)
        row2.pack(fill="x", pady=4)
        
        ttk.Label(row2, text="Extensões (vírgula):").pack(side="left")
        
        self.ent_exts = ttk.Entry(row2)
        self.ent_exts.pack(side="left", fill="x", expand=True, padx=6)
        self.ent_exts.insert(0, ", ".join(DEFAULT_EXTS))
    
    def _setup_ignore_section(self, parent: ttk.Frame) -> None:
        """Configura seção de diretórios a ignorar."""
        row3 = ttk.Frame(parent)
        row3.pack(fill="x", pady=4)
        
        ttk.Label(row3, text="Ignorar diretórios (extra):").pack(side="left")
        
        self.ent_ignore = ttk.Entry(row3)
        self.ent_ignore.pack(side="left", fill="x", expand=True, padx=6)
        self.ent_ignore.insert(0, "")
    
    def _setup_options_section(self, parent: ttk.Frame) -> None:
        """Configura seção de opções de formatação."""
        row4 = ttk.Frame(parent)
        row4.pack(fill="x", pady=6)
        
        # Criação dos checkboxes (usando variáveis já criadas no __init__)
        ttk.Checkbutton(
            row4,
            text="Incluir ocultos",
            variable=self.var_hidden
        ).pack(side="left")
        
        ttk.Checkbutton(
            row4,
            text="Separador forte",
            variable=self.var_strong
        ).pack(side="left", padx=(12, 0))
        
        ttk.Checkbutton(
            row4,
            text="Seção recolhível",
            variable=self.var_collapse
        ).pack(side="left", padx=(12, 0))
        
        ttk.Checkbutton(
            row4,
            text="Incluir SHA-1",
            variable=self.var_hash
        ).pack(side="left", padx=(12, 0))
        
        ttk.Checkbutton(
            row4,
            text="Quebra de página",
            variable=self.var_pagebreak
        ).pack(side="left", padx=(12, 0))
    
    def _setup_title_section(self, parent: ttk.Frame) -> None:
        """Configura seção de título do documento."""
        rowt = ttk.Frame(parent)
        rowt.pack(fill="x", pady=6)
        
        ttk.Label(rowt, text="Título:").grid(row=0, column=0, sticky="w")
        
        self.ent_title = ttk.Entry(rowt)
        self.ent_title.grid(row=0, column=1, sticky="ew", padx=6)
        self.ent_title.insert(0, "Pacote Unificado de Código")
        
        # Configuração de expansão da coluna
        rowt.columnconfigure(1, weight=1)
    
    def _setup_split_section(self, parent: ttk.Frame) -> None:
        """Configura seção de divisão em múltiplos arquivos."""
        rowsplit = ttk.Frame(parent)
        rowsplit.pack(fill="x", pady=6)
        
        ttk.Label(
            rowsplit,
            text="Dividir em quantos arquivos:"
        ).pack(side="left")
        
        self.spin_parts = tk.Spinbox(
            rowsplit,
            from_=1,
            to=50,
            width=5
        )
        self.spin_parts.delete(0, "end")
        self.spin_parts.insert(0, "1")
        self.spin_parts.pack(side="left", padx=6)
    
    def _setup_output_section(self, parent: ttk.Frame) -> None:
        """Configura seção de saída/nome dos arquivos."""
        rowsave = ttk.Frame(parent)
        rowsave.pack(fill="x", pady=6)
        
        ttk.Label(
            rowsave,
            text="Padrão do nome (sem extensão):"
        ).pack(side="left")
        
        self.ent_basename = ttk.Entry(rowsave)
        self.ent_basename.pack(side="left", fill="x", expand=True, padx=6)
        self.ent_basename.insert(0, "codigo_unificado")
        
        ttk.Button(
            rowsave,
            text="Escolher pasta de saída…",
            command=self.choose_outdir
        ).pack(side="left")
        
        # Label para mostrar pasta selecionada
        ttk.Label(
            rowsave,
            textvariable=self.outdir_var,
            foreground="#666"
        ).pack(side="left", padx=6)
    
    def _setup_action_section(self, parent: ttk.Frame) -> None:
        """Configura seção de botões de ação."""
        row5 = ttk.Frame(parent)
        row5.pack(fill="x", pady=10)
        
        # Botão de pré-visualização
        ttk.Button(
            row5,
            text="Pré-visualizar (contar)",
            command=self.preview
        ).pack(side="left")
        
        # Botão principal de geração
        ttk.Button(
            row5,
            text="Gerar Documentação",
            command=self.generate
        ).pack(side="right")
    
    def _setup_list_section(self, parent: ttk.Frame) -> None:
        """Configura seção de lista de arquivos detectados."""
        lst_wrap = ttk.Frame(parent)
        lst_wrap.pack(fill="both", expand=True, pady=(8, 0))
        
        # Listbox com scrollbar
        self.lst = tk.Listbox(lst_wrap, height=20, selectmode=tk.EXTENDED)
        self.lst.pack(side="left", fill="both", expand=True)
        
        scroll = ttk.Scrollbar(
            lst_wrap,
            orient="vertical",
            command=self.lst.yview
        )
        scroll.pack(side="right", fill="y")
        
        # Conexão bidirecional
        self.lst.config(yscrollcommand=scroll.set)
    
    def _setup_footer(self, parent: ttk.Frame) -> None:
        """Configura rodapé com informações de status."""
        footer = ttk.Frame(parent)
        footer.pack(fill="x", pady=6)
        
        self.lbl_info = ttk.Label(
            footer,
            text="Selecione uma pasta e clique em 'Pré-visualizar' para começar."
        )
        self.lbl_info.pack(side="left")
    
    # ========================================================================
    # HANDLERS DE EVENTOS DA INTERFACE
    # ========================================================================
    
    def choose_root(self) -> None:
        """Abre diálogo para seleção da pasta raiz."""
        d = filedialog.askdirectory(title="Escolha a pasta raiz do projeto")
        if d:
            self.ent_root.delete(0, tk.END)
            self.ent_root.insert(0, d)
    
    def choose_outdir(self) -> None:
        """Abre diálogo para seleção da pasta de saída."""
        d = filedialog.askdirectory(title="Escolha a pasta de saída")
        if d:
            self.outdir_var.set(d)
    
    def get_exts(self) -> Set[str]:
        """
        Extrai e valida extensões da entrada do usuário.
        
        Returns:
            Conjunto de extensões válidas (com ponto inicial)
        """
        raw = self.ent_exts.get().strip()
        
        # Processamento de tokens com múltiplos separadores
        tokens = [t.strip().lower() for t in raw.replace(";", ",").split(",") if t.strip()]
        
        exts = []
        for t in tokens:
            if not t.startswith("."):
                t = "." + t
            exts.append(t)
        
        # Fallback para padrão se entrada vazia
        return set(exts) if exts else set(DEFAULT_EXTS)
    
    def preview(self) -> None:
        """
        Executa pré-visualização: varre arquivos e exibe na lista.
        
        VALIDAÇÕES:
            - Pasta raiz existe
            - É um diretório válido
        """
        root = Path(self.ent_root.get().strip() or ".").resolve()
        
        if not root.exists() or not root.is_dir():
            messagebox.showwarning(
                "Aviso",
                "Informe uma pasta raiz válida."
            )
            return
        
        # Obtém extensões configuradas
        exts = self.get_exts()
        
        # Executa varredura
        files = scan_files(
            root,
            exts,
            include_hidden=self.var_hidden.get(),
            ignore_dirs_extra=self.ent_ignore.get().strip()
        )
        
        # Atualiza interface
        self.lst.delete(0, tk.END)
        for p in files:
            try:
                self.lst.insert(tk.END, p.relative_to(root).as_posix())
            except ValueError:
                self.lst.insert(tk.END, str(p))
        
        # Atualiza status
        self.lbl_info.config(
            text=f"{len(files)} arquivo(s) encontrados para processamento."
        )
    
    def generate(self) -> None:
        """
        Fluxo principal de geração: processa arquivos e gera documentação.
        
        ETAPAS:
            1. Validação de entrada
            2. Varredura de arquivos
            3. Configuração de saída
            4. Processamento e divisão
            5. Geração dos arquivos Markdown
        """
        # Validação da pasta raiz
        root = Path(self.ent_root.get().strip() or ".").resolve()
        
        if not root.exists() or not root.is_dir():
            messagebox.showwarning(
                "Aviso",
                "Informe uma pasta raiz válida."
            )
            return
        
        # Varredura inicial
        exts = self.get_exts()
        files = scan_files(
            root,
            exts,
            include_hidden=self.var_hidden.get(),
            ignore_dirs_extra=self.ent_ignore.get().strip()
        )
        
        if not files:
            messagebox.showwarning(
                "Aviso",
                "Nenhum arquivo correspondente encontrado com os filtros atuais."
            )
            return
        
        # Configuração de divisão
        try:
            parts = int(self.spin_parts.get())
        except ValueError:
            parts = 1
        
        # Limites razoáveis
        parts = max(1, min(50, parts))
        
        # Configuração de pasta de saída
        outdir: Optional[Path] = None
        if self.outdir_var.get().strip():
            outdir = Path(self.outdir_var.get().strip())
        
        # Fallback: pedir ao usuário se não configurado
        if not outdir:
            tmp = filedialog.asksaveasfilename(
                title="Escolha a pasta e nome base para saída",
                defaultextension=".md",
                filetypes=[("Markdown", "*.md"), ("Texto", "*.txt")],
                initialfile="codigo_unificado.md",
            )
            
            if not tmp:
                return  # Usuário cancelou
            
            outdir = Path(tmp).parent
        
        # Garante que outdir não é None
        if outdir is None:
            messagebox.showerror("Erro", "Nenhuma pasta de saída selecionada.")
            return
        
        # Parâmetros de formatação
        basename = self.ent_basename.get().strip() or "codigo_unificado"
        titulo = self.ent_title.get().strip() or "Pacote Unificado de Código"
        
        strong = self.var_strong.get()
        collapsible = self.var_collapse.get()
        include_hash = self.var_hash.get()
        page_break = self.var_pagebreak.get()
        
        try:
            # Distribuição balanceada por tamanho
            buckets = distribute_by_size(files, parts)
            
            # Caso de arquivo único
            if parts == 1:
                destino = outdir / f"{basename}.md"
                
                write_unified_md(
                    destino,
                    root,
                    buckets[0],
                    titulo,
                    strong,
                    collapsible,
                    include_hash,
                    page_break,
                    1,
                    1
                )
                
                messagebox.showinfo(
                    "Sucesso",
                    f"Documentação gerada com sucesso:\n{destino}"
                )
            
            # Caso de múltiplos arquivos
            else:
                created: List[str] = []
                
                # Determina padding para numeração (01, 02, ...)
                digits = max(2, len(str(parts)))
                
                # Gera cada parte
                for i, group in enumerate(buckets, 1):
                    destino = outdir / f"{basename}_parte_{str(i).zfill(digits)}.md"
                    
                    write_unified_md(
                        destino,
                        root,
                        group,
                        titulo,
                        strong,
                        collapsible,
                        include_hash,
                        page_break,
                        i,
                        parts
                    )
                    
                    created.append(destino.as_posix())
                
                # Relatório de sucesso
                msg = "Documentação gerada em múltiplos arquivos:\n\n" + "\n".join(created)
                messagebox.showinfo("Sucesso", msg)
        
        except Exception as e:
            messagebox.showerror(
                "Erro na Geração",
                f"Ocorreu um erro durante o processamento:\n\n{str(e)}"
            )


# ============================================================================
# PONTO DE ENTRADA DA APLICAÇÃO
# ============================================================================


if __name__ == "__main__":
    """
    Ponto de entrada principal da aplicação Code Unifier Pro.
    
    EXECUÇÃO:
        python code_unifier_pro.py
    
    DEPENDÊNCIAS:
        - Python 3.8+
        - Tkinter (geralmente incluído)
        - Nenhuma dependência externa adicional
    
    NOTAS:
        - Aplicação standalone sem instalação necessária
        - Compatível com Windows, macOS e Linux
        - Persistência de configurações: não implementada nesta versão
    """
    
    # Cria e executa a aplicação
    app = CodeUnifierPro()
    
    # Configuração de estilo (opcional, mas melhora aparência)
    try:
        style = ttk.Style()
        style.theme_use('clam')  # Tema moderno se disponível
    except:
        pass  # Usa tema padrão se falhar
    
    # Inicia loop principal de eventos
    app.mainloop()
