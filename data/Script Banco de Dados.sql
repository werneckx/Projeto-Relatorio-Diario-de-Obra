CREATE DATABASE IF NOT EXISTS rdo_platform_db
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE rdo_platform_db;

/* =========================
   DROP (ORDEM REVERSA)
========================= */

DROP TABLE IF EXISTS rdo_aprovacoes;
DROP TABLE IF EXISTS rdo_fotos;
DROP TABLE IF EXISTS rdo_atividades;
DROP TABLE IF EXISTS rdo_ocorrencias;
DROP TABLE IF EXISTS rdo_equipamentos;
DROP TABLE IF EXISTS rdo_mao_obra;
DROP TABLE IF EXISTS rdo;

DROP TABLE IF EXISTS frente_colaborador;
DROP TABLE IF EXISTS frente_trabalho;
DROP TABLE IF EXISTS obra_usuario;
DROP TABLE IF EXISTS obras;
DROP TABLE IF EXISTS clientes;

DROP TABLE IF EXISTS papel_permissao;
DROP TABLE IF EXISTS usuario_papel;
DROP TABLE IF EXISTS permissoes;
DROP TABLE IF EXISTS papeis;

DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS colaboradores;
DROP TABLE IF EXISTS fornecedores;

DROP TABLE IF EXISTS aux_tag_ocorrencia;
DROP TABLE IF EXISTS aux_tipo_obra;
DROP TABLE IF EXISTS aux_equipamentos;
DROP TABLE IF EXISTS aux_funcoes;
DROP TABLE IF EXISTS aux_clima;

DROP TABLE IF EXISTS empresa;

/* =========================
   EMPRESA (BASE)
========================= */

CREATE TABLE empresa (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    logo_empresa VARCHAR(255),
    icone_empresa VARCHAR(255),
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   AUXILIARES
========================= */

CREATE TABLE aux_clima (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NULL,              -- NULL = padrão global do sistema
    descricao VARCHAR(100) NOT NULL,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_clima_empresa (empresa_id, descricao),
    INDEX idx_clima_empresa (empresa_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE aux_funcoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NULL,              -- NULL = padrão global do sistema
    descricao VARCHAR(100) NOT NULL,
    tipo ENUM('DIRETO','INDIRETO'),
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_funcao_empresa (empresa_id, descricao),
    INDEX idx_funcao_empresa (empresa_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE aux_equipamentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NULL,              -- NULL = padrão global do sistema
    descricao VARCHAR(150) NOT NULL,
    tipo VARCHAR(100),
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_equip_empresa (empresa_id, descricao),
    INDEX idx_equip_empresa (empresa_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE aux_tag_ocorrencia (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NULL,              -- NULL = padrão global do sistema
    descricao VARCHAR(150) NOT NULL,
    tipo VARCHAR(100),
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_tag_empresa (empresa_id, descricao),
    INDEX idx_tag_empresa (empresa_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE aux_tipo_obra (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NULL,              -- NULL = padrão global do sistema
    nome VARCHAR(100) NOT NULL,
    descricao TEXT,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_tipo_obra_empresa (empresa_id, nome),
    INDEX idx_tipo_obra_empresa (empresa_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   RBAC
   empresa_id NULL = escopo global (is_system)
   Roles e permissões is_system não podem ser deletados
========================= */

CREATE TABLE papeis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NULL,                           -- NULL = global do sistema
    nome VARCHAR(100) NOT NULL,
    descricao TEXT,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,       -- TRUE = imutável
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_papel_empresa (empresa_id, nome),
    INDEX idx_papel_empresa (empresa_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE permissoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NULL,                           -- NULL = global do sistema
    chave VARCHAR(100) NOT NULL,
    descricao TEXT,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_perm_empresa (empresa_id, chave),
    INDEX idx_perm_empresa (empresa_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE papel_permissao (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NULL,
    papel_id INT NOT NULL,
    permissao_id INT NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,

    INDEX idx_pp_empresa (empresa_id),
    INDEX idx_pp_papel (papel_id),
    INDEX idx_pp_perm (permissao_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (papel_id) REFERENCES papeis(id),
    FOREIGN KEY (permissao_id) REFERENCES permissoes(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   FORNECEDORES
========================= */

CREATE TABLE fornecedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    cnpj VARCHAR(20),
    endereco TEXT,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_forn_empresa (empresa_id),
    UNIQUE KEY uk_forn_cnpj_empresa (empresa_id, cnpj),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   CLIENTES
========================= */

CREATE TABLE clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,

    razao_social VARCHAR(200) NOT NULL,
    nome_fantasia VARCHAR(200),
    cnpj VARCHAR(18) NOT NULL,

    contato_nome VARCHAR(150),
    contato_email VARCHAR(150),
    contato_telefone VARCHAR(30),

    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_cliente_empresa_cnpj (empresa_id, cnpj),
    INDEX idx_cliente_empresa (empresa_id),
    INDEX idx_clientes_cnpj (cnpj),

    CONSTRAINT fk_cliente_empresa
        FOREIGN KEY (empresa_id) REFERENCES empresa(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   COLABORADORES / USUÁRIOS
========================= */

CREATE TABLE colaboradores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    fornecedor_id INT NULL,                        -- NULL = colaborador próprio
    cliente_id INT NULL,                           -- NULL = se não for tipo CLIENTE
    tipo ENUM('PROPRIO','TERCEIRO','CLIENTE') NOT NULL DEFAULT 'PROPRIO',
    cadastro_pessoa_fisica VARCHAR(100),
    nome VARCHAR(150) NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_colab_empresa_doc (empresa_id, cadastro_pessoa_fisica),
    INDEX idx_colab_empresa (empresa_id),
    INDEX idx_colab_fornecedor (fornecedor_id),
    INDEX idx_colab_cliente (cliente_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id),
    CONSTRAINT fk_colab_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    
    CONSTRAINT chk_colab_tipo CHECK (
        (tipo = 'PROPRIO' AND fornecedor_id IS NULL AND cliente_id IS NULL) OR
        (tipo = 'TERCEIRO' AND fornecedor_id IS NOT NULL AND cliente_id IS NULL) OR
        (tipo = 'CLIENTE' AND cliente_id IS NOT NULL AND fornecedor_id IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    colaborador_id INT,
    email VARCHAR(150) NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    ultimo_login DATETIME,
    ultimo_login_ip VARCHAR(45),

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_user_email_empresa (empresa_id, email),
    INDEX idx_user_empresa (empresa_id),
    INDEX idx_user_colab (colaborador_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (colaborador_id) REFERENCES colaboradores(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE usuario_papel (
    empresa_id INT NOT NULL,
    usuario_id INT NOT NULL,
    papel_id INT NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,

    PRIMARY KEY (empresa_id, usuario_id, papel_id),

    INDEX idx_up_empresa (empresa_id),
    INDEX idx_up_usuario (usuario_id),
    INDEX idx_up_papel (papel_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (papel_id) REFERENCES papeis(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   OBRAS
========================= */

CREATE TABLE obras (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    data_inicio DATE,
    data_fim_planejada DATE,
    data_fim DATE,

    -- Responsável
    usuario_responsavel_id INT NULL,

    -- Tipo de Obra
    tipo_obra_id INT NULL,

    -- Vínculo com Cliente
    cliente_id INT NOT NULL,
    cnpj_obra VARCHAR(20),

    -- Endereço Normalizado
    logradouro VARCHAR(200),
    numero VARCHAR(20),
    complemento VARCHAR(100),
    bairro VARCHAR(100),
    cidade VARCHAR(100),
    estado CHAR(2),
    cep VARCHAR(10),

    hora_entrada_padrao TIME,
    intervalo_entrada_padrao TIME,
    intervalo_saida_padrao TIME,
    hora_saida_padrao TIME,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_obras_empresa (empresa_id),
    INDEX idx_obras_usuario_responsavel (usuario_responsavel_id),
    INDEX idx_obras_tipo (tipo_obra_id),
    INDEX idx_obras_cidade (cidade),
    INDEX idx_obras_cliente (cliente_id),
    INDEX idx_obras_empresa_cliente (empresa_id, cliente_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (usuario_responsavel_id) REFERENCES usuarios(id),
    FOREIGN KEY (tipo_obra_id) REFERENCES aux_tipo_obra(id),
    CONSTRAINT fk_obras_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   FRENTE DE TRABALHO
========================= */

CREATE TABLE frente_trabalho (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    obra_id INT NOT NULL,
    nome VARCHAR(150),
    centro_custo VARCHAR(100),
    data_inicio DATE,
    data_fim_planejada DATE,
    data_fim DATE,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_frente_empresa (empresa_id),
    INDEX idx_frente_obra (obra_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (obra_id) REFERENCES obras(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE obra_usuario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    obra_id INT NOT NULL,
    usuario_id INT NOT NULL,
    papel_id INT,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_ou_empresa (empresa_id),
    INDEX idx_ou_obra (obra_id),
    INDEX idx_ou_usuario (usuario_id),
    INDEX idx_ou_papel (papel_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (obra_id) REFERENCES obras(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (papel_id) REFERENCES papeis(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE frente_colaborador (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    frente_id INT NOT NULL,
    colaborador_id INT NOT NULL,
    funcao_id INT,
    data_inicio DATE,
    data_fim DATE,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_fc_empresa (empresa_id),
    INDEX idx_fc_frente (frente_id),
    INDEX idx_fc_colab (colaborador_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (frente_id) REFERENCES frente_trabalho(id),
    FOREIGN KEY (colaborador_id) REFERENCES colaboradores(id),
    FOREIGN KEY (funcao_id) REFERENCES aux_funcoes(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   RDO
========================= */

CREATE TABLE rdo (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    obra_id INT NOT NULL,
    numero_sequencial INT,
    frente_trabalho_id INT NOT NULL,
    data_rdo DATE,
    status ENUM('PENDENTE','APROVADO','REJEITADO') DEFAULT 'PENDENTE',

    clima_manha_id INT,
    clima_tarde_id INT,

    hora_entrada TIME,
    hora_saida TIME,
    intervalo_entrada TIME,
    intervalo_saida TIME,

    observacoes TEXT,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_rdo_sequencial (obra_id, numero_sequencial),
    INDEX idx_rdo_empresa (empresa_id),
    INDEX idx_rdo_obra (obra_id),
    INDEX idx_rdo_data (data_rdo),
    INDEX idx_rdo_status (status),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (obra_id) REFERENCES obras(id),
    FOREIGN KEY (frente_trabalho_id) REFERENCES frente_trabalho(id),
    FOREIGN KEY (clima_manha_id) REFERENCES aux_clima(id),
    FOREIGN KEY (clima_tarde_id) REFERENCES aux_clima(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   RDO MAO DE OBRA
========================= */

CREATE TABLE rdo_mao_obra (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    rdo_id INT NOT NULL,
    colaborador_id INT NOT NULL,
    funcao VARCHAR(100),
    quantidade_horas DECIMAL(10,2),
    tipo_mao_obra ENUM('PROPRIA','TERCEIRO'),
    observacao TEXT,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_rmo_empresa (empresa_id),
    INDEX idx_rmo_rdo (rdo_id),
    INDEX idx_rmo_colab (colaborador_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (rdo_id) REFERENCES rdo(id),
    FOREIGN KEY (colaborador_id) REFERENCES colaboradores(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   RDO EQUIPAMENTOS
========================= */

CREATE TABLE rdo_equipamentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    rdo_id INT NOT NULL,
    equipamento_id INT NOT NULL,
    quantidade INT,
    horas_utilizadas DECIMAL(10,2),
    status ENUM('OPERANDO','PARADO'),
    motivo_parada TEXT,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_re_empresa (empresa_id),
    INDEX idx_re_rdo (rdo_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (rdo_id) REFERENCES rdo(id),
    FOREIGN KEY (equipamento_id) REFERENCES aux_equipamentos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   OCORRENCIAS
========================= */

CREATE TABLE rdo_ocorrencias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    rdo_id INT NOT NULL,
    tipo_ocorrencia INT,
    descricao TEXT,
    impacto ENUM('BAIXO','MEDIO','ALTO'),
    tempo_paralisacao DECIMAL(10,2),
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_ro_empresa (empresa_id),
    INDEX idx_ro_rdo (rdo_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (rdo_id) REFERENCES rdo(id),
    FOREIGN KEY (tipo_ocorrencia) REFERENCES aux_tag_ocorrencia(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   ATIVIDADES
========================= */

CREATE TABLE rdo_atividades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    rdo_id INT NOT NULL,
    descricao TEXT,
    status VARCHAR(50),
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_ra_empresa (empresa_id),
    INDEX idx_ra_rdo (rdo_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (rdo_id) REFERENCES rdo(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   FOTOS
========================= */

CREATE TABLE rdo_fotos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    rdo_id INT NOT NULL,
    arquivo VARCHAR(255),
    comentario TEXT,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_rf_empresa (empresa_id),
    INDEX idx_rf_rdo (rdo_id),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (rdo_id) REFERENCES rdo(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   APROVACAO
========================= */

CREATE TABLE rdo_aprovacoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    rdo_id INT NOT NULL,
    aprovador_id INT NOT NULL,
    nivel INT,
    status ENUM('PENDENTE','APROVADO','REJEITADO') DEFAULT 'PENDENTE',
    data_aprovacao DATETIME,
    comentario TEXT,
    endereco_ip VARCHAR(45),
    hash VARCHAR(255), -- Hash da assinatura SHA256
    imagem_assinatura TEXT,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_rdo_nivel (rdo_id, nivel),

    INDEX idx_ra_empresa (empresa_id),
    INDEX idx_ra_status_nivel (status, nivel),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (rdo_id) REFERENCES rdo(id),
    FOREIGN KEY (aprovador_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   TRIGGERS
========================= */

DELIMITER //

CREATE TRIGGER trg_rdo_numero_sequencial
BEFORE INSERT ON rdo
FOR EACH ROW
BEGIN
    DECLARE proximo_numero INT;
    SELECT COALESCE(MAX(numero_sequencial), 0) + 1 INTO proximo_numero
    FROM rdo
    WHERE obra_id = NEW.obra_id;
    SET NEW.numero_sequencial = proximo_numero;
END //

DELIMITER ;

/* =========================
   SEED – ROLES E PERMISSÕES GLOBAIS DO SISTEMA
   empresa_id = NULL / is_system = TRUE
   Não podem ser deletados ou editados
========================= */

-- Papéis do Sistema
INSERT INTO papeis (empresa_id, nome, descricao, is_system, ativo) VALUES
(NULL, 'ADMIN',        'Controle total sobre a empresa',                     TRUE, TRUE),
(NULL, 'GESTOR',       'Gestão operacional: RDO, equipes, aprovações',       TRUE, TRUE),
(NULL, 'OPERADOR',     'Input operacional: lançamentos de RDO',              TRUE, TRUE),
(NULL, 'LEITOR',       'Somente leitura de dados da empresa',                TRUE, TRUE),
(NULL, 'CLIENTE_OBRA', 'Acesso externo restrito: visualização e assinatura', TRUE, TRUE);

-- Permissões do Sistema
INSERT INTO permissoes (empresa_id, chave, descricao, is_system, ativo) VALUES
(NULL, 'empresa.create',    'Criar novas empresas no sistema',         TRUE, TRUE),
(NULL, 'empresa.view',      'Visualizar dados da empresa',             TRUE, TRUE),
(NULL, 'empresa.manage',    'Gerenciar configurações da empresa',      TRUE, TRUE),
(NULL, 'usuario.manage',    'Gerenciar usuários da empresa',           TRUE, TRUE),
(NULL, 'rdo.create',        'Criar novos RDOs',                        TRUE, TRUE),
(NULL, 'rdo.update',        'Editar RDOs existentes',                  TRUE, TRUE),
(NULL, 'rdo.approve',       'Aprovar ou rejeitar RDOs',                TRUE, TRUE),
(NULL, 'rdo.view',          'Visualizar RDOs',                         TRUE, TRUE),
(NULL, 'fornecedor.manage', 'Gerenciar fornecedores da empresa',       TRUE, TRUE),
(NULL, 'obra.manage',       'Gerenciar obras e frentes de trabalho',   TRUE, TRUE),
(NULL, 'colaborador.manage','Gerenciar colaboradores e equipes',       TRUE, TRUE);

-- Mapeamento ADMIN → todas as permissões
INSERT INTO papel_permissao (empresa_id, papel_id, permissao_id, ativo)
SELECT NULL, p.id, perm.id, TRUE
FROM papeis p, permissoes perm
WHERE p.nome = 'ADMIN' AND p.empresa_id IS NULL AND perm.empresa_id IS NULL;

-- Mapeamento GESTOR
INSERT INTO papel_permissao (empresa_id, papel_id, permissao_id, ativo)
SELECT NULL, p.id, perm.id, TRUE
FROM papeis p, permissoes perm
WHERE p.nome = 'GESTOR' AND p.empresa_id IS NULL
  AND perm.empresa_id IS NULL
  AND perm.chave IN ('empresa.view','usuario.manage','rdo.create','rdo.update','rdo.approve','rdo.view','fornecedor.manage','obra.manage','colaborador.manage');

-- Mapeamento OPERADOR
INSERT INTO papel_permissao (empresa_id, papel_id, permissao_id, ativo)
SELECT NULL, p.id, perm.id, TRUE
FROM papeis p, permissoes perm
WHERE p.nome = 'OPERADOR' AND p.empresa_id IS NULL
  AND perm.empresa_id IS NULL
  AND perm.chave IN ('rdo.create','rdo.update','rdo.view','empresa.view','colaborador.manage');

-- Mapeamento LEITOR
INSERT INTO papel_permissao (empresa_id, papel_id, permissao_id, ativo)
SELECT NULL, p.id, perm.id, TRUE
FROM papeis p, permissoes perm
WHERE p.nome = 'LEITOR' AND p.empresa_id IS NULL
  AND perm.empresa_id IS NULL
  AND perm.chave IN ('rdo.view','empresa.view');

-- Mapeamento CLIENTE_OBRA
INSERT INTO papel_permissao (empresa_id, papel_id, permissao_id, ativo)
SELECT NULL, p.id, perm.id, TRUE
FROM papeis p, permissoes perm
WHERE p.nome = 'CLIENTE_OBRA' AND p.empresa_id IS NULL
  AND perm.empresa_id IS NULL
  AND perm.chave IN ('rdo.view','rdo.approve');

-- Aux Clima
INSERT INTO aux_clima (empresa_id, descricao, is_system, ativo) VALUES
(NULL, 'Bom', TRUE, TRUE),
(NULL, 'Chuvoso', TRUE, TRUE),
(NULL, 'Nublado', TRUE, TRUE),
(NULL, 'Impraticável', TRUE, TRUE);

-- Aux Funções (Mão de Obra)
INSERT INTO aux_funcoes (empresa_id, descricao, tipo, is_system, ativo) VALUES
(NULL, 'Engenheiro', 'DIRETO', TRUE, TRUE),
(NULL, 'Encarregado', 'DIRETO', TRUE, TRUE),
(NULL, 'Pedreiro', 'DIRETO', TRUE, TRUE),
(NULL, 'Servente', 'DIRETO', TRUE, TRUE),
(NULL, 'Carpinteiro', 'DIRETO', TRUE, TRUE),
(NULL, 'Armador', 'DIRETO', TRUE, TRUE),
(NULL, 'Eletricista', 'DIRETO', TRUE, TRUE),
(NULL, 'Encanador', 'DIRETO', TRUE, TRUE),
(NULL, 'Motorista', 'INDIRETO', TRUE, TRUE),
(NULL, 'Operador de Máquinas', 'DIRETO', TRUE, TRUE),
(NULL, 'Técnico de Segurança', 'INDIRETO', TRUE, TRUE),
(NULL, 'Administrativo', 'INDIRETO', TRUE, TRUE);

-- Aux Equipamentos
INSERT INTO aux_equipamentos (empresa_id, descricao, tipo, is_system, ativo) VALUES
(NULL, 'Escavadeira Hidráulica', 'Pesado', TRUE, TRUE),
(NULL, 'Retroescavadeira', 'Pesado', TRUE, TRUE),
(NULL, 'Motoniveladora', 'Pesado', TRUE, TRUE),
(NULL, 'Rolo Compactador', 'Pesado', TRUE, TRUE),
(NULL, 'Caminhão Basculante', 'Transporte', TRUE, TRUE),
(NULL, 'Caminhão Pipa', 'Transporte', TRUE, TRUE),
(NULL, 'Caminhão Munck', 'Transporte', TRUE, TRUE),
(NULL, 'Betoneira', 'Leve', TRUE, TRUE),
(NULL, 'Placa Compactadora', 'Leve', TRUE, TRUE),
(NULL, 'Gerador', 'Leve', TRUE, TRUE),
(NULL, 'Compressor de Ar', 'Leve', TRUE, TRUE);

-- Aux Tag Ocorrência
INSERT INTO aux_tag_ocorrencia (empresa_id, descricao, tipo, is_system, ativo) VALUES
(NULL, 'Falta de Material', 'Atraso', TRUE, TRUE),
(NULL, 'Quebra de Equipamento', 'Atraso', TRUE, TRUE),
(NULL, 'Falta de Energia', 'Atraso', TRUE, TRUE),
(NULL, 'Condições Climáticas', 'Paralisação', TRUE, TRUE),
(NULL, 'Acidente de Trabalho', 'Segurança', TRUE, TRUE),
(NULL, 'Aguardando Liberação', 'Atraso', TRUE, TRUE),
(NULL, 'Aguardando Definição de Projeto', 'Atraso', TRUE, TRUE),
(NULL, 'Falta de Mão de Obra', 'Atraso', TRUE, TRUE),
(NULL, 'Aguardando Cliente', 'Atraso', TRUE, TRUE),
(NULL, 'Retrabalho', 'Qualidade', TRUE, TRUE),
(NULL, 'Aguardando Inspeção', 'Qualidade', TRUE, TRUE);

-- Aux Tipo Obra
INSERT INTO aux_tipo_obra (empresa_id, nome, descricao, is_system, ativo) VALUES
(NULL, 'Saneamento', 'Obras de redes de água, esgoto e tratamento.', TRUE, TRUE),
(NULL, 'Óleo e Gás', 'Obras em refinarias, dutos e plataformas.', TRUE, TRUE),
(NULL, 'Infraestrutura', 'Obras de estradas, pontes e vias urbanas.', TRUE, TRUE),
(NULL, 'Industrial', 'Construção e manutenção de plantas industriais.', TRUE, TRUE),
(NULL, 'Energia', 'Obras em subestações e linhas de transmissão.', TRUE, TRUE);

/* ==========================================================
   SCRIPT DE SEED PARA DEMONSTRAÇÃO (RDO PLATFORM)
   Este script assume que as tabelas base e os dados de 
   sistema (is_system = TRUE) já foram inseridos.
   ========================================================== */

USE rdo_platform_db;

-- 1. Inserir Empresa de Demonstração
INSERT INTO empresa (id, nome, logo_empresa, icone_empresa) VALUES
(1, 'Construções Horizonte S.A.', 'https://img.logo/horizonte.png', 'https://img.logo/icon_h.png');

-- 2. Inserir Fornecedores
INSERT INTO fornecedores (id, empresa_id, nome, cnpj, endereco) VALUES
(1, 1, 'LocaMáquinas Brasil', '11.222.333/0001-44', 'Rua Industrial, 100 - SP'),
(2, 1, 'Mão de Obra Especializada Ltda', '55.444.333/0001-22', 'Av. Central, 500 - RJ');

-- 3. Inserir Colaboradores (Próprios e Terceiros)
-- Próprios
INSERT INTO colaboradores (id, empresa_id, fornecedor_id, tipo, cadastro_pessoa_fisica, nome) VALUES
(1, 1, NULL, 'PROPRIO', '123.456.789-00', 'Ricardo Silva (Gestor)'),
(2, 1, NULL, 'PROPRIO', '222.333.444-55', 'João Pereira (Engenheiro)'),
(3, 1, NULL, 'PROPRIO', '999.888.777-66', 'Ana Costa (Operadora)');

-- Terceiros
INSERT INTO colaboradores (id, empresa_id, fornecedor_id, tipo, cadastro_pessoa_fisica, nome) VALUES
(4, 1, 2, 'TERCEIRO', '444.555.666-77', 'Carlos Pedreiro (Terceirizado)'),
(5, 1, 2, 'TERCEIRO', '111.000.111-22', 'Marcos Ajudante (Terceirizado)');

-- Clientes (Stakeholders)
INSERT INTO colaboradores (id, empresa_id, cliente_id, tipo, nome) VALUES
(6, 1, 1, 'CLIENTE', 'Supervisor Bella Vista (Cliente)');

-- 4. Inserir Usuários (Acesso ao Sistema)
-- Senha padrão para demo: 'password123' (hash simplificado para exemplo)
INSERT INTO usuarios (id, empresa_id, colaborador_id, email, senha_hash) VALUES
(1, 1, 1, 'gestor@horizonte.com.br', '$2y$10$eImiTXuWVxfM37uY4JANjOL.oMqpzh07YlC2v8t/1W/K9/u6hVnd.'),
(2, 1, 3, 'operador@horizonte.com.br', '$2y$10$eImiTXuWVxfM37uY4JANjOL.oMqpzh07YlC2v8t/1W/K9/u6hVnd.'),
(3, 1, 6, 'supervisor@bellavista.com.br', '$2y$10$eImiTXuWVxfM37uY4JANjOL.oMqpzh07YlC2v8t/1W/K9/u6hVnd.');

-- 5. Atribuir Papéis aos Usuários
-- Assumindo IDs do script original: 1=ADMIN, 2=GESTOR, 3=OPERADOR
INSERT INTO usuario_papel (empresa_id, usuario_id, papel_id) VALUES
(1, 1, 1), -- Ricardo é ADMIN (Acesso Total)
(1, 2, 3), -- Ana é OPERADOR
(1, 3, 3); -- Supervisor do Cliente com papel OPERADOR (ou um novo papelStakeholder)

-- 6. Inserir Clientes
INSERT INTO clientes (id, empresa_id, razao_social, nome_fantasia, cnpj, contato_nome, contato_email) VALUES
(1, 1, 'Incorporadora Bella Vista Ltda', 'Bella Vista Inc', '12.345.678/0001-90', 'Marcos Oliveira', 'contato@bellavista.com.br'),
(2, 1, 'Sky Tower Empreendimentos S.A.', 'Sky Corp', '98.765.432/0001-10', 'Julia Santos', 'vendas@skycorp.com');

-- 7. Inserir Obras
INSERT INTO obras (id, empresa_id, nome, data_inicio, data_fim_planejada, tipo_obra_id, usuario_responsavel_id, cliente_id, cidade, estado, hora_entrada_padrao, hora_saida_padrao) VALUES
(1, 1, 'Residencial Bella Vista', '2023-10-01', '2025-12-31', 4, 1, 1, 'São Paulo', 'SP', '07:00:00', '17:00:00'),
(2, 1, 'Edifício Comercial Sky', '2024-01-15', '2026-06-30', 4, 1, 2, 'Rio de Janeiro', 'RJ', '08:00:00', '18:00:00');

-- 8. Inserir Frentes de Trabalho
INSERT INTO frente_trabalho (id, empresa_id, obra_id, nome, centro_custo) VALUES
(1, 1, 1, 'Fundação e Estrutura', 'CC-2023-01'),
(2, 1, 1, 'Instalações Elétricas', 'CC-2023-02'),
(3, 1, 2, 'Terraplenagem', 'CC-2024-01');

-- 8. Vincular Colaboradores às Frentes de Trabalho
-- (Supondo que Engenheiro=1, Pedreiro=3 no aux_funcoes do sistema)
INSERT INTO frente_colaborador (empresa_id, frente_id, colaborador_id, funcao_id, data_inicio) VALUES
(1, 1, 2, 1, '2023-10-01'), -- João Engenheiro na Fundação
(1, 1, 4, 3, '2023-10-01'), -- Carlos Pedreiro na Fundação
(1, 1, 5, 4, '2023-10-01'); -- Marcos Servente na Fundação

-- 9. Exemplo de RDO Lançado (Cenário de Teste)
-- Criando um RDO para o dia anterior
INSERT INTO rdo (id, empresa_id, obra_id, frente_trabalho_id, data_rdo, status, clima_manha_id, clima_tarde_id, observacoes, criado_por) VALUES
(1, 1, 1, 1, CURDATE() - INTERVAL 1 DAY, 'PENDENTE', 1, 3, 'Dia produtivo, apesar da nebulosidade no período da tarde.', 2);

-- 10. Dados Detalhados do RDO (Mão de Obra, Equipamentos, Atividades)
-- Mão de Obra no RDO
INSERT INTO rdo_mao_obra (empresa_id, rdo_id, colaborador_id, quantidade_horas, tipo_mao_obra) VALUES
(1, 1, 4, 8.00, 'TERCEIRO'),
(1, 1, 5, 8.00, 'TERCEIRO');

-- Equipamentos no RDO (Supondo Escavadeira=1 do aux_equipamentos)
INSERT INTO rdo_equipamentos (empresa_id, rdo_id, equipamento_id, quantidade, horas_utilizadas, status) VALUES
(1, 1, 1, 1, 6.50, 'OPERANDO');

-- Atividades no RDO
INSERT INTO rdo_atividades (empresa_id, rdo_id, descricao, status) VALUES
(1, 1, 'Escavação manual de blocos da fundação', 'Concluído'),
(1, 1, 'Lançamento de concreto magro', 'Em Andamento');

-- Ocorrências (Supondo Falta de Material=1 do aux_tag_ocorrencia)
INSERT INTO rdo_ocorrencias (empresa_id, rdo_id, tipo_ocorrencia, descricao, impacto, tempo_paralisacao) VALUES
(1, 1, 1, 'Atraso na entrega de brita por parte do fornecedor local.', 'MEDIO', 2.00);

-- Fotos do RDO
INSERT INTO rdo_fotos (empresa_id, rdo_id, arquivo, comentario) VALUES
(1, 1, 'https://storage.demo/rdo_1_foto_1.jpg', 'Vista geral da escavação dos blocos.');