CREATE DATABASE IF NOT EXISTS rdo_platform_db
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE rdo_platform_db;

-- Padrão do sistema: persistir timestamps em UTC.
-- A conversão para o timezone da empresa/obra é feita na aplicação via empresa_config/obra_config.
SET time_zone = '+00:00';

SET FOREIGN_KEY_CHECKS = 0;

/* =========================
   DROP (ORDEM REVERSA)
========================= */

DROP TABLE IF EXISTS acesso_log;
DROP TABLE IF EXISTS sessoes_usuario;
DROP TABLE IF EXISTS arquivos;
DROP TABLE IF EXISTS notificacoes;
DROP TABLE IF EXISTS workflow_etapas;
DROP TABLE IF EXISTS workflow_definicoes;
DROP TABLE IF EXISTS rdo_versoes;
DROP TABLE IF EXISTS obra_config;
DROP TABLE IF EXISTS empresa_config;
DROP TABLE IF EXISTS config_definicoes;
DROP TABLE IF EXISTS rdo_assinaturas;
DROP TABLE IF EXISTS rdo_aprovacoes;
DROP TABLE IF EXISTS rdo_fotos;
DROP TABLE IF EXISTS auditoria_log;
DROP TABLE IF EXISTS rdo_atividades;
DROP TABLE IF EXISTS rdo_ocorrencias;
DROP TABLE IF EXISTS rdo_equipamentos;
DROP TABLE IF EXISTS rdo_mao_obra;
DROP TABLE IF EXISTS rdo;

DROP TABLE IF EXISTS frente_colaborador;
DROP TABLE IF EXISTS frente_trabalho;
DROP TABLE IF EXISTS obra_usuario;
DROP TABLE IF EXISTS obras;

DROP TABLE IF EXISTS papel_permissao;
DROP TABLE IF EXISTS usuario_papel;
DROP TABLE IF EXISTS permissoes;
DROP TABLE IF EXISTS papeis;

DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS colaboradores;
DROP TABLE IF EXISTS clientes;
DROP TABLE IF EXISTS fornecedores;

DROP TABLE IF EXISTS aux_tag_ocorrencia;
DROP TABLE IF EXISTS aux_tipo_obra;
DROP TABLE IF EXISTS aux_equipamentos;
DROP TABLE IF EXISTS aux_funcoes;
DROP TABLE IF EXISTS aux_clima;

DROP TABLE IF EXISTS cad_listas;
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
   MASTER LIST (GOVERNANÇA)
========================= */

CREATE TABLE cad_listas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NULL,
    titulo VARCHAR(150) NOT NULL,
    nome_interno VARCHAR(150) NOT NULL,
    slug VARCHAR(150) NOT NULL,
    descricao TEXT,
    modulo ENUM('RDO', 'Estoque', 'Suprimentos', 'Administrativo', 'RH', 'Configuração', 'Integração', 'Financeiro', 'Engenharia', 'Sistema') NOT NULL,
    tipo_lista ENUM('Auxiliar', 'Cadastro', 'Transacional', 'Configuração', 'Auditoria', 'Log', 'Sistema') NOT NULL,
    origem_dados ENUM('SharePoint', 'SQL Server', 'MySQL', 'Dataverse', 'API Externa') NOT NULL,
    versao_estrutura VARCHAR(20) DEFAULT 'v1.0',
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,
    permite_edicao_usuario BOOLEAN DEFAULT FALSE,
    sincronizar_integracoes BOOLEAN DEFAULT FALSE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_lista_nome_interno (nome_interno),
    UNIQUE KEY uk_lista_slug (empresa_id, slug),
    INDEX idx_lista_empresa (empresa_id),
    INDEX idx_lista_modulo (modulo),
    INDEX idx_lista_tipo (tipo_lista),
    INDEX idx_lista_ativo (ativo),

    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (criado_por) REFERENCES usuarios(id),
    FOREIGN KEY (modificado_por) REFERENCES usuarios(id)
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
    CONSTRAINT fk_colab_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    colaborador_id INT,
    email VARCHAR(150) NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    is_system BOOLEAN DEFAULT FALSE,
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
    status ENUM('RASCUNHO','PENDENTE','APROVADO','REJEITADO','CANCELADO') DEFAULT 'RASCUNHO',
    versao INT NOT NULL DEFAULT 1,
    rdo_origem_id INT NULL,
    bloqueado_em DATETIME NULL,
    bloqueado_por INT NULL,

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
    FOREIGN KEY (rdo_origem_id) REFERENCES rdo(id),
    FOREIGN KEY (bloqueado_por) REFERENCES usuarios(id),
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
   VERSIONAMENTO DO RDO
========================= */

CREATE TABLE rdo_versoes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    rdo_id INT NOT NULL,
    numero_versao INT NOT NULL,
    motivo VARCHAR(255),
    dados_snapshot JSON NOT NULL,
    hash_snapshot VARCHAR(255),
    criado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_rdo_versao (rdo_id, numero_versao),
    INDEX idx_rdo_versao_empresa (empresa_id),
    INDEX idx_rdo_versao_rdo (rdo_id),

    CONSTRAINT fk_rdo_versao_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    CONSTRAINT fk_rdo_versao_rdo FOREIGN KEY (rdo_id) REFERENCES rdo(id),
    CONSTRAINT fk_rdo_versao_usuario FOREIGN KEY (criado_por) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE documentos_sistema {
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    tipo ENUM(
        'TERMOS_USO',
        'POLITICA_PRIVACIDADE',
        'SUPORTE',
        'POLITICA_COOKIES',
        'FAQ',
        'MANUAL',
        'OUTRO'
    ) NOT NULL,
    titulo VARCHAR(255) NOT NULL,
    conteudo TEXT NOT NULL,
    versao VARCHAR(20) NOT NULL DEFAULT 'v1.0',
    publicado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_documento_empresa
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id),

    CONSTRAINT fk_documento_criado_por
        FOREIGN KEY (criado_por)
        REFERENCES usuario(id),

    CONSTRAINT fk_documento_modificado_por
        FOREIGN KEY (modificado_por)
        REFERENCES usuario(id)
};

CREATE TABLE usuario_documento_aceite (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,

    usuario_id BIGINT NOT NULL,
    documento_id BIGINT NOT NULL,

    ip VARCHAR(50),
    aceito_em DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_aceite_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuario(id),

    CONSTRAINT fk_aceite_documento
        FOREIGN KEY (documento_id)
        REFERENCES documentos_sistema(id)
);

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
(NULL, 'usuario.manage',   'Gerenciar usuários da empresa',           TRUE, TRUE),
(NULL, 'rdo.create',        'Criar novos RDOs',                        TRUE, TRUE),
(NULL, 'rdo.update',        'Editar RDOs existentes',                  TRUE, TRUE),
(NULL, 'rdo.approve',       'Aprovar ou rejeitar RDOs',                TRUE, TRUE),
(NULL, 'rdo.view',          'Visualizar RDOs',                         TRUE, TRUE),
(NULL, 'rdo.sign',         'Assinar RDOs no fluxo',                 TRUE, TRUE),
(NULL, 'rdo.reject',       'Rejeitar assinaturas no fluxo',          TRUE, TRUE),
(NULL, 'fornecedor.manage','Gerenciar fornecedores da empresa',       TRUE, TRUE),
(NULL, 'obra.manage',      'Gerenciar obras e frentes de trabalho',   TRUE, TRUE),
(NULL, 'colaborador.manage','Gerenciar colaboradores e equipes',      TRUE, TRUE),


-- Auxiliares (clima)
(NULL, 'clima.view',       'Visualizar climas',                      TRUE, TRUE),
(NULL, 'clima.create',     'Criar climas',                            TRUE, TRUE),
(NULL, 'clima.update',     'Editar climas',                           TRUE, TRUE),
(NULL, 'clima.delete',     'Excluir climas',                          TRUE, TRUE),

-- Auxiliares (equipamentos)
(NULL, 'equipamento.view',   'Visualizar equipamentos',               TRUE, TRUE),
(NULL, 'equipamento.create', 'Criar equipamentos',                    TRUE, TRUE),
(NULL, 'equipamento.update', 'Editar equipamentos',                   TRUE, TRUE),
(NULL, 'equipamento.delete', 'Excluir equipamentos',                  TRUE, TRUE),

-- Auxiliares (mão de obra)
(NULL, 'mao_obra.view',    'Visualizar mão de obra',                 TRUE, TRUE),
(NULL, 'mao_obra.create',  'Criar mão de obra',                      TRUE, TRUE),
(NULL, 'mao_obra.update',  'Editar mão de obra',                     TRUE, TRUE),
(NULL, 'mao_obra.delete',  'Excluir mão de obra',                    TRUE, TRUE),

-- Auxiliares (tags de ocorrências)
(NULL, 'tag_ocorrencia.view',   'Visualizar tags de ocorrências',     TRUE, TRUE),
(NULL, 'tag_ocorrencia.create', 'Criar tags de ocorrências',          TRUE, TRUE),
(NULL, 'tag_ocorrencia.update', 'Editar tags de ocorrências',         TRUE, TRUE),
(NULL, 'tag_ocorrencia.delete', 'Excluir tags de ocorrências',        TRUE, TRUE);

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

-- 3. Inserir Clientes
INSERT INTO clientes (id, empresa_id, razao_social, nome_fantasia, cnpj, contato_nome, contato_email) VALUES
(1, 1, 'Incorporadora Bella Vista Ltda', 'Bella Vista Inc', '12.345.678/0001-90', 'Marcos Oliveira', 'contato@bellavista.com.br'),
(2, 1, 'Sky Tower Empreendimentos S.A.', 'Sky Corp', '98.765.432/0001-10', 'Julia Santos', 'vendas@skycorp.com');

-- 4. Inserir Colaboradores (Próprios e Terceiros)
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

-- 5. Inserir Usuários (Acesso ao Sistema)
-- Senha padrão para demo: 'admin' (hash simplificado para exemplo)
-- Ajuste de IDs para criar ADMIN MASTER com id=1
-- antes: 1=gestor(ADMIN), 2=operador, 3=supervisor
-- agora: 1=admin master, 2=ex-usuario 1, 3=ex-usuario 2, 4=ex-usuario 3
INSERT INTO usuarios (id, empresa_id, colaborador_id, email, senha_hash, is_system) VALUES
(1, 2, 1, 'admin@nosde.com.br', 'scrypt:32768:8:1$NMXQmJ4GCOJVmNoe$c62100d1b8d581dddc096ec887df55f1a716ab08c8cbd8f6ff16eae875822597681b6b29e4633ef098f281d3b7ab47c7b8540be065efe25605c1ac82a441dbf8', TRUE), -- ADMIN MASTER (Acesso Total, sem vínculo com empresa específica)
(2, 1, 3, 'operador@horizonte.com.br', 'scrypt:32768:8:1$NMXQmJ4GCOJVmNoe$c62100d1b8d581dddc096ec887df55f1a716ab08c8cbd8f6ff16eae875822597681b6b29e4633ef098f281d3b7ab47c7b8540be065efe25605c1ac82a441dbf8', FALSE),
(3, 1, 6, 'supervisor@bellavista.com.br', 'scrypt:32768:8:1$NMXQmJ4GCOJVmNoe$c62100d1b8d581dddc096ec887df55f1a716ab08c8cbd8f6ff16eae875822597681b6b29e4633ef098f281d3b7ab47c7b8540be065efe25605c1ac82a441dbf8', FALSE),
(4, 1, 1, 'gestor@horizonte.com.br', 'scrypt:32768:8:1$NMXQmJ4GCOJVmNoe$c62100d1b8d581dddc096ec887df55f1a716ab08c8cbd8f6ff16eae875822597681b6b29e4633ef098f281d3b7ab47c7b8540be065efe25605c1ac82a441dbf8', FALSE);

-- 6. Atribuir Papéis aos Usuários
-- Após ajuste: 1=ADMIN MASTER, 2=ex-usuario 1, 3=ex-usuario 2
INSERT INTO usuario_papel (empresa_id, usuario_id, papel_id) VALUES
(1, 1, 1), -- admin.master é ADMIN (Acesso Total)
(1, 2, 3), -- operador
(1, 3, 3), -- supervisor
(1, 4, 3); -- gestor legado vira operador (mantém FKs do seed)

-- 7. Inserir Obras
INSERT INTO obras (id, empresa_id, nome, data_inicio, data_fim_planejada, tipo_obra_id, usuario_responsavel_id, cliente_id, cidade, estado, hora_entrada_padrao, hora_saida_padrao) VALUES
(1, 1, 'Residencial Bella Vista', '2023-10-01', '2025-12-31', 4, 1, 1, 'São Paulo', 'SP', '07:00:00', '17:00:00'),
(2, 1, 'Edifício Comercial Sky', '2024-01-15', '2026-06-30', 4, 1, 2, 'Rio de Janeiro', 'RJ', '08:00:00', '18:00:00');

-- 8. Inserir Frentes de Trabalho
INSERT INTO frente_trabalho (id, empresa_id, obra_id, nome, centro_custo) VALUES
(1, 1, 1, 'Fundação e Estrutura', 'CC-2023-01'),
(2, 1, 1, 'Instalações Elétricas', 'CC-2023-02'),
(3, 1, 2, 'Terraplenagem', 'CC-2024-01');

-- 9. Vincular Colaboradores às Frentes de Trabalho
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

/* =========================
   AUDITORIA E RASTREABILIDADE
========================= */

CREATE TABLE auditoria_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    usuario_id INT NULL,
    colaborador_id INT NULL,
    acao VARCHAR(50) NOT NULL,
    entidade VARCHAR(50) NOT NULL,
    entidade_id INT NULL,
    dados_antes JSON NULL,
    dados_depois JSON NULL,
    ip VARCHAR(45),
    user_agent VARCHAR(255),
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_audit_empresa (empresa_id),
    INDEX idx_audit_usuario (usuario_id),
    INDEX idx_audit_entidade (entidade, entidade_id),
    INDEX idx_audit_data (criado_em),

    CONSTRAINT fk_audit_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    CONSTRAINT fk_audit_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT fk_audit_colaborador FOREIGN KEY (colaborador_id) REFERENCES colaboradores(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE rdo_assinaturas (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    rdo_id INT NOT NULL,
    usuario_id INT NOT NULL,
    colaborador_id INT NOT NULL,
    tipo_assinatura ENUM('INTERNO','CLIENTE') NOT NULL,
    status ENUM('ASSINADO','REJEITADO', 'PENDENTE') NOT NULL,
    hash_documento VARCHAR(255) NOT NULL,
    ip VARCHAR(45),
    user_agent VARCHAR(255),
    assinado_em DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_rdo_assinatura_rdo (rdo_id),
    INDEX idx_rdo_assinatura_usuario (usuario_id),

    CONSTRAINT fk_rdo_ass_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    CONSTRAINT fk_rdo_ass_rdo FOREIGN KEY (rdo_id) REFERENCES rdo(id),
    CONSTRAINT fk_rdo_ass_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT fk_rdo_ass_colab FOREIGN KEY (colaborador_id) REFERENCES colaboradores(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   SISTEMA DE CONFIGURAÇÕES
========================= */

/* =========================
   WORKFLOW CONFIGURAVEL
========================= */

CREATE TABLE workflow_definicoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    obra_id INT NULL,
    nome VARCHAR(150) NOT NULL,
    descricao TEXT,
    aprovacao_paralela BOOLEAN NOT NULL DEFAULT FALSE,
    rejeicao_cancela_fluxo BOOLEAN NOT NULL DEFAULT TRUE,
    sla_horas INT NULL,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_workflow_empresa (empresa_id),
    INDEX idx_workflow_obra (obra_id),
    UNIQUE KEY uk_workflow_empresa_obra_nome (empresa_id, obra_id, nome),

    CONSTRAINT fk_workflow_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    CONSTRAINT fk_workflow_obra FOREIGN KEY (obra_id) REFERENCES obras(id),
    CONSTRAINT fk_workflow_criado_por FOREIGN KEY (criado_por) REFERENCES usuarios(id),
    CONSTRAINT fk_workflow_modificado_por FOREIGN KEY (modificado_por) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE workflow_etapas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    workflow_id INT NOT NULL,
    nivel INT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    papel_id INT NULL,
    usuario_aprovador_id INT NULL,
    obrigatorio BOOLEAN NOT NULL DEFAULT TRUE,
    sla_horas INT NULL,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_workflow_etapa_nivel (workflow_id, nivel),
    INDEX idx_workflow_etapa_empresa (empresa_id),
    INDEX idx_workflow_etapa_papel (papel_id),
    INDEX idx_workflow_etapa_usuario (usuario_aprovador_id),

    CONSTRAINT fk_workflow_etapa_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    CONSTRAINT fk_workflow_etapa_workflow FOREIGN KEY (workflow_id) REFERENCES workflow_definicoes(id),
    CONSTRAINT fk_workflow_etapa_papel FOREIGN KEY (papel_id) REFERENCES papeis(id),
    CONSTRAINT fk_workflow_etapa_usuario FOREIGN KEY (usuario_aprovador_id) REFERENCES usuarios(id),
    CONSTRAINT fk_workflow_etapa_criado_por FOREIGN KEY (criado_por) REFERENCES usuarios(id),
    CONSTRAINT fk_workflow_etapa_modificado_por FOREIGN KEY (modificado_por) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   NOTIFICACOES
========================= */

CREATE TABLE notificacoes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    usuario_id INT NULL,
    obra_id INT NULL,
    rdo_id INT NULL,
    tipo ENUM('APROVACAO_PENDENTE','NOVO_RDO','ALERTA','REJEICAO','AVISO_OPERACIONAL','SISTEMA') NOT NULL,
    titulo VARCHAR(150) NOT NULL,
    mensagem TEXT,
    link VARCHAR(255),
    lida BOOLEAN NOT NULL DEFAULT FALSE,
    lida_em DATETIME NULL,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_notif_empresa (empresa_id),
    INDEX idx_notif_usuario_lida (usuario_id, lida),
    INDEX idx_notif_obra (obra_id),
    INDEX idx_notif_rdo (rdo_id),
    INDEX idx_notif_tipo (tipo),

    CONSTRAINT fk_notif_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    CONSTRAINT fk_notif_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT fk_notif_obra FOREIGN KEY (obra_id) REFERENCES obras(id),
    CONSTRAINT fk_notif_rdo FOREIGN KEY (rdo_id) REFERENCES rdo(id),
    CONSTRAINT fk_notif_criado_por FOREIGN KEY (criado_por) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   ARQUIVOS E DOCUMENTOS
========================= */

CREATE TABLE arquivos (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    obra_id INT NULL,
    rdo_id INT NULL,
    entidade VARCHAR(80) NULL,
    entidade_id INT NULL,
    categoria ENUM('PDF','IMAGEM','ART','CONTRATO','ANEXO','DOCUMENTO','OUTRO') NOT NULL DEFAULT 'ANEXO',
    nome_original VARCHAR(255) NOT NULL,
    nome_armazenado VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100),
    tamanho_bytes BIGINT NULL,
    storage_provider ENUM('LOCAL','S3','AZURE','MINIO') NOT NULL DEFAULT 'LOCAL',
    storage_path VARCHAR(500) NOT NULL,
    hash_arquivo VARCHAR(255),
    publico BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,

    criado_por INT NULL,
    modificado_por INT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_arquivo_empresa (empresa_id),
    INDEX idx_arquivo_obra (obra_id),
    INDEX idx_arquivo_rdo (rdo_id),
    INDEX idx_arquivo_entidade (entidade, entidade_id),
    INDEX idx_arquivo_categoria (categoria),

    CONSTRAINT fk_arquivo_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    CONSTRAINT fk_arquivo_obra FOREIGN KEY (obra_id) REFERENCES obras(id),
    CONSTRAINT fk_arquivo_rdo FOREIGN KEY (rdo_id) REFERENCES rdo(id),
    CONSTRAINT fk_arquivo_criado_por FOREIGN KEY (criado_por) REFERENCES usuarios(id),
    CONSTRAINT fk_arquivo_modificado_por FOREIGN KEY (modificado_por) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   SESSOES E LOGS DE ACESSO
========================= */

CREATE TABLE sessoes_usuario (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    usuario_id INT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    ip VARCHAR(45),
    user_agent VARCHAR(255),
    iniciada_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    expira_em DATETIME NOT NULL,
    encerrada_em DATETIME NULL,
    encerrada_por INT NULL,
    motivo_encerramento VARCHAR(100),
    ativa BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE KEY uk_sessao_token_hash (token_hash),
    INDEX idx_sessao_empresa (empresa_id),
    INDEX idx_sessao_usuario_ativa (usuario_id, ativa),
    INDEX idx_sessao_expira (expira_em),

    CONSTRAINT fk_sessao_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    CONSTRAINT fk_sessao_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT fk_sessao_encerrada_por FOREIGN KEY (encerrada_por) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE acesso_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NULL,
    usuario_id INT NULL,
    email VARCHAR(150),
    acao ENUM('LOGIN_SUCESSO','LOGIN_FALHA','LOGOUT','LOGOUT_REMOTO','SESSAO_EXPIRADA','SENHA_REDEFINIDA') NOT NULL,
    ip VARCHAR(45),
    user_agent VARCHAR(255),
    detalhes JSON NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_acesso_empresa (empresa_id),
    INDEX idx_acesso_usuario (usuario_id),
    INDEX idx_acesso_email (email),
    INDEX idx_acesso_acao_data (acao, criado_em),

    CONSTRAINT fk_acesso_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    CONSTRAINT fk_acesso_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/* =========================
   SISTEMA DE CONFIGURACOES
========================= */

CREATE TABLE config_definicoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    chave VARCHAR(100) NOT NULL UNIQUE,
    descricao TEXT,
    tipo ENUM('BOOLEAN', 'STRING', 'INT', 'JSON') NOT NULL,
    valor_padrao TEXT,
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_config_def_chave (chave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE empresa_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    chave VARCHAR(100) NOT NULL,
    valor TEXT,
    
    UNIQUE KEY uk_empresa_config (empresa_id, chave),
    CONSTRAINT fk_empresa_config_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id) ON DELETE CASCADE,
    CONSTRAINT fk_empresa_config_chave FOREIGN KEY (chave) REFERENCES config_definicoes(chave) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE obra_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    obra_id INT NOT NULL,
    chave VARCHAR(100) NOT NULL,
    valor TEXT,

    UNIQUE KEY uk_obra_config (obra_id, chave),
    CONSTRAINT fk_obra_config_empresa FOREIGN KEY (empresa_id) REFERENCES empresa(id) ON DELETE CASCADE,
    CONSTRAINT fk_obra_config_obra FOREIGN KEY (obra_id) REFERENCES obras(id) ON DELETE CASCADE,
    CONSTRAINT fk_obra_config_chave FOREIGN KEY (chave) REFERENCES config_definicoes(chave) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed Inicial de Configurações
INSERT INTO config_definicoes (chave, descricao, tipo, valor_padrao) VALUES
('workflow.aprovacao.ordem', 'Ordem dos aprovadores no workflow do RDO', 'JSON', '["RESPONSAVEL_OBRA", "CLIENTE"]'),
('workflow.aprovacao.obrigatorio', 'Define se o RDO exige aprovação formal', 'BOOLEAN', 'true'),
('rdo.secoes.atividades', 'Habilitar seção de atividades no RDO', 'BOOLEAN', 'true'),
('rdo.secoes.ocorrencias', 'Habilitar seção de ocorrências no RDO', 'BOOLEAN', 'true'),
('rdo.secoes.mao_obra', 'Habilitar seção de mão de obra no RDO', 'BOOLEAN', 'true'),
('rdo.secoes.equipamentos', 'Habilitar seção de equipamentos no RDO', 'BOOLEAN', 'true'),
('rdo.secoes.fotos', 'Habilitar seção de fotos no RDO', 'BOOLEAN', 'true'),
('assinatura.modo', 'Modo de assinatura (HASH_ONLY ou COM_IMAGEM)', 'STRING', 'HASH_ONLY'),
('assinatura.capturar_ip', 'Registrar IP na assinatura', 'BOOLEAN', 'true'),
('assinatura.capturar_user_agent', 'Registrar User Agent na assinatura', 'BOOLEAN', 'true');

-- Seed Inicial de Listas (Governança)
INSERT INTO config_definicoes (chave, descricao, tipo, valor_padrao) VALUES
('workflow.aprovacao.paralela', 'Permitir aprovacao paralela quando configurada', 'BOOLEAN', 'false'),
('workflow.aprovacao.sla_horas', 'SLA padrao de aprovacao em horas', 'INT', '48'),
('sessao.timeout_minutos', 'Tempo padrao para expiracao de sessao', 'INT', '480'),
('upload.storage_provider', 'Provedor padrao para armazenamento de arquivos', 'STRING', 'LOCAL'),
('timezone', 'Timezone IANA da empresa/obra (ex.: America/Sao_Paulo)', 'STRING', 'UTC'),
('empresa.tema_cor_primaria', 'Cor primaria padrao do tema da empresa', 'STRING', '#0F766E'),
('empresa.tema_cor_secundaria', 'Cor secundaria padrao do tema da empresa', 'STRING', '#1F2937'),
('empresa.dark_mode', 'Habilitar modo escuro por padrao', 'BOOLEAN', 'false');

INSERT INTO cad_listas (titulo, nome_interno, slug, modulo, tipo_lista, origem_dados, is_system, ativo) VALUES
-- SISTEMA E CONFIGURAÇÃO
('Catálogo de Listas', 'cad_listas', 'cad-listas', 'Sistema', 'Sistema', 'MySQL', TRUE, TRUE),
('Empresas', 'empresa', 'empresa', 'Sistema', 'Cadastro', 'MySQL', TRUE, TRUE),
('Usuários', 'usuarios', 'usuarios', 'Sistema', 'Cadastro', 'MySQL', TRUE, TRUE),
('Papéis de Acesso', 'papeis', 'papeis', 'Sistema', 'Configuração', 'MySQL', TRUE, TRUE),
('Permissões', 'permissoes', 'permissoes', 'Sistema', 'Configuração', 'MySQL', TRUE, TRUE),
('Mapeamento Papel/Permissão', 'papel_permissao', 'papel-permissao', 'Sistema', 'Configuração', 'MySQL', TRUE, TRUE),
('Mapeamento Usuário/Papel', 'usuario_papel', 'usuario-papel', 'Sistema', 'Configuração', 'MySQL', TRUE, TRUE),
('Definições de Configuração', 'config_definicoes', 'config-definicoes', 'Sistema', 'Configuração', 'MySQL', TRUE, TRUE),
('Configurações da Empresa', 'empresa_config', 'empresa-config', 'Sistema', 'Configuração', 'MySQL', TRUE, TRUE),
('Log de Auditoria', 'auditoria_log', 'auditoria-log', 'Sistema', 'Log', 'MySQL', TRUE, TRUE),

-- CADASTROS GERAIS
('Colaboradores', 'colaboradores', 'colaboradores', 'RH', 'Cadastro', 'MySQL', TRUE, TRUE),
('Clientes', 'clientes', 'clientes', 'Administrativo', 'Cadastro', 'MySQL', TRUE, TRUE),
('Fornecedores', 'fornecedores', 'fornecedores', 'Suprimentos', 'Cadastro', 'MySQL', TRUE, TRUE),

-- ENGENHARIA E OBRAS
('Tipos de Obra', 'aux_tipo_obra', 'tipos-de-obra', 'Engenharia', 'Auxiliar', 'MySQL', TRUE, TRUE),
('Obras', 'obras', 'obras', 'Engenharia', 'Cadastro', 'MySQL', TRUE, TRUE),
('Frentes de Trabalho', 'frente_trabalho', 'frentes-de-trabalho', 'Engenharia', 'Cadastro', 'MySQL', TRUE, TRUE),
('Usuários da Obra', 'obra_usuario', 'obra-usuario', 'Engenharia', 'Configuração', 'MySQL', TRUE, TRUE),
('Colaboradores da Frente', 'frente_colaborador', 'frente-colaborador', 'Engenharia', 'Configuração', 'MySQL', TRUE, TRUE),
('Configurações da Obra', 'obra_config', 'obra-config', 'Engenharia', 'Configuração', 'MySQL', TRUE, TRUE),

-- RDO (AUXILIARES)
('Clima', 'aux_clima', 'clima', 'RDO', 'Auxiliar', 'MySQL', TRUE, TRUE),
('Funções de Mão de Obra', 'aux_funcoes', 'funcoes-mao-obra', 'RDO', 'Auxiliar', 'MySQL', TRUE, TRUE),
('Equipamentos', 'aux_equipamentos', 'equipamentos', 'RDO', 'Auxiliar', 'MySQL', TRUE, TRUE),
('Tags de Ocorrência', 'aux_tag_ocorrencia', 'tags-ocorrencia', 'RDO', 'Auxiliar', 'MySQL', TRUE, TRUE),

-- RDO (TRANSACIONAL)
('RDO (Capa)', 'rdo', 'rdo', 'RDO', 'Transacional', 'MySQL', TRUE, TRUE),
('RDO - Mão de Obra', 'rdo_mao_obra', 'rdo-mao-obra', 'RDO', 'Transacional', 'MySQL', TRUE, TRUE),
('RDO - Equipamentos', 'rdo_equipamentos', 'rdo-equipamentos', 'RDO', 'Transacional', 'MySQL', TRUE, TRUE),
('RDO - Atividades', 'rdo_atividades', 'rdo-atividades', 'RDO', 'Transacional', 'MySQL', TRUE, TRUE),
('RDO - Ocorrências', 'rdo_ocorrencias', 'rdo-ocorrencias', 'RDO', 'Transacional', 'MySQL', TRUE, TRUE),
('RDO - Fotos', 'rdo_fotos', 'rdo-fotos', 'RDO', 'Transacional', 'MySQL', TRUE, TRUE),
('RDO - Aprovações', 'rdo_aprovacoes', 'rdo-aprovacoes', 'RDO', 'Transacional', 'MySQL', TRUE, TRUE),
('RDO - Assinaturas', 'rdo_assinaturas', 'rdo-assinaturas', 'RDO', 'Transacional', 'MySQL', TRUE, TRUE),
('RDO - Versoes', 'rdo_versoes', 'rdo-versoes', 'RDO', 'Auditoria', 'MySQL', TRUE, TRUE),
('Workflows de Aprovacao', 'workflow_definicoes', 'workflow-definicoes', 'Sistema', 'Sistema', 'MySQL', TRUE, TRUE),
('Etapas do Workflow', 'workflow_etapas', 'workflow-etapas', 'Sistema', 'Sistema', 'MySQL', TRUE, TRUE),
('Notificacoes', 'notificacoes', 'notificacoes', 'Sistema', 'Transacional', 'MySQL', TRUE, TRUE),
('Arquivos e Documentos', 'arquivos', 'arquivos', 'Sistema', 'Cadastro', 'MySQL', TRUE, TRUE),
('Sessoes de Usuario', 'sessoes_usuario', 'sessoes-usuario', 'Sistema', 'Log', 'MySQL', TRUE, TRUE),
('Log de Acesso', 'acesso_log', 'acesso-log', 'Sistema', 'Log', 'MySQL', TRUE, TRUE);

/* ==========================================================
   SEED CORPORATIVO COMPLETO - EMPRESA REALISTA
   Massa de dados para validar todas as tabelas do modelo.
   ========================================================== */

-- Empresa
INSERT INTO empresa (id, nome, logo_empresa, icone_empresa, ativo, criado_em) VALUES
(2, 'Enfil SA Controle Ambiental', 'uploads/logos/logo_empresa_2.png', 'uploads/logos/icone_empresa_2.png', TRUE, NOW());

-- Configuracoes da empresa
INSERT INTO empresa_config (empresa_id, chave, valor) VALUES
(2, 'workflow.aprovacao.ordem', '["RESPONSAVEL_OBRA","GESTOR_CONTRATO","CLIENTE"]'),
(2, 'workflow.aprovacao.obrigatorio', 'true'),
(2, 'workflow.aprovacao.paralela', 'false'),
(2, 'workflow.aprovacao.sla_horas', '24'),
(2, 'sessao.timeout_minutos', '600'),
(2, 'upload.storage_provider', 'LOCAL'),
(2, 'timezone', 'America/Sao_Paulo'),
(2, 'empresa.tema_cor_primaria', '#005F73'),
(2, 'empresa.tema_cor_secundaria', '#0A9396'),
(2, 'empresa.dark_mode', 'false');

-- Cadastros auxiliares especificos da empresa
INSERT INTO aux_clima (id, empresa_id, descricao, is_system, ativo) VALUES
(20, 2, 'Sol forte', FALSE, TRUE),
(21, 2, 'Chuva intermitente', FALSE, TRUE);

INSERT INTO aux_funcoes (id, empresa_id, descricao, tipo, is_system, ativo) VALUES
(20, 2, 'Supervisor de Campo', 'DIRETO', FALSE, TRUE),
(21, 2, 'Soldador PEAD', 'DIRETO', FALSE, TRUE),
(22, 2, 'Assistente Administrativo de Obra', 'INDIRETO', FALSE, TRUE);

INSERT INTO aux_equipamentos (id, empresa_id, descricao, tipo, is_system, ativo) VALUES
(20, 2, 'Escavadeira CAT 320', 'Pesado', FALSE, TRUE),
(21, 2, 'Caminhao Poliguindaste', 'Transporte', FALSE, TRUE),
(22, 2, 'Bomba Submersivel 3CV', 'Leve', FALSE, TRUE);

INSERT INTO aux_tag_ocorrencia (id, empresa_id, descricao, tipo, is_system, ativo) VALUES
(20, 2, 'Interferencia de rede existente', 'Engenharia', FALSE, TRUE),
(21, 2, 'Aguardando liberacao da concessionaria', 'Atraso', FALSE, TRUE);

INSERT INTO aux_tipo_obra (id, empresa_id, nome, descricao, is_system, ativo) VALUES
(20, 2, 'ETE - Estacao de Tratamento', 'Implantacao e ampliacao de estacoes de tratamento de esgoto.', FALSE, TRUE);

-- RBAC especifico da empresa
INSERT INTO papeis (id, empresa_id, nome, descricao, is_system, ativo) VALUES
(20, 2, 'GESTOR_CONTRATO', 'Gestor responsavel por contratos e medicoes da empresa.', FALSE, TRUE);

INSERT INTO permissoes (empresa_id, chave, descricao, is_system, ativo) VALUES
(2, 'medicao.view', 'Visualizar dados de medicao e produtividade da obra.', FALSE, TRUE),
(2, 'workflow.manage', 'Gerenciar workflows de aprovacao da empresa.', FALSE, TRUE);

INSERT INTO papel_permissao (id, empresa_id, papel_id, permissao_id, ativo) VALUES
(100, 2, 20, 20, TRUE),
(101, 2, 20, 21, TRUE);

-- Fornecedores e clientes
INSERT INTO fornecedores (id, empresa_id, nome, cnpj, endereco, ativo, criado_por) VALUES
(20, 2, 'Terraplenagem Rio Claro Ltda', '42.778.991/0001-30', 'Rodovia SP-330, km 118 - Campinas/SP', TRUE, NULL),
(21, 2, 'Locadora Atlas Equipamentos Pesados', '18.455.220/0001-88', 'Av. Industrial, 1250 - Jundiai/SP', TRUE, NULL);

INSERT INTO clientes (id, empresa_id, razao_social, nome_fantasia, cnpj, contato_nome, contato_email, contato_telefone, ativo) VALUES
(20, 2, 'Companhia Municipal de Saneamento de Campinas', 'SANECAMP', '07.123.456/0001-55', 'Marina Andrade', 'marina.andrade@sanecamp.example', '(19) 3333-4400', TRUE);

-- Colaboradores e usuarios
INSERT INTO colaboradores (id, empresa_id, fornecedor_id, cliente_id, tipo, cadastro_pessoa_fisica, nome, ativo) VALUES
(20, 2, NULL, NULL, 'PROPRIO', '310.450.780-10', 'Paulo Mendes - Diretor de Operacoes', TRUE),
(21, 2, NULL, NULL, 'PROPRIO', '225.778.990-44', 'Camila Rocha - Gestora de Contrato', TRUE),
(22, 2, NULL, NULL, 'PROPRIO', '144.555.222-91', 'Rafael Nunes - Engenheiro Residente', TRUE),
(23, 2, NULL, NULL, 'PROPRIO', '090.321.777-85', 'Beatriz Lima - Tecnica de Seguranca', TRUE),
(24, 2, 20, NULL, 'TERCEIRO', '418.200.771-66', 'Jose Carlos - Operador de Escavadeira', TRUE),
(25, 2, 20, NULL, 'TERCEIRO', '301.778.120-43', 'Mateus Vieira - Soldador PEAD', TRUE),
(26, 2, NULL, 20, 'CLIENTE', '771.441.992-10', 'Marina Andrade - Fiscal SANECAMP', TRUE);

INSERT INTO usuarios (id, empresa_id, colaborador_id, email, senha_hash, ativo, ultimo_login, ultimo_login_ip) VALUES
(20, 2, 20, 'diretoria@enfil.com.br', 'scrypt:32768:8:1$NMXQmJ4GCOJVmNoe$c62100d1b8d581dddc096ec887df55f1a716ab08c8cbd8f6ff16eae875822597681b6b29e4633ef098f281d3b7ab47c7b8540be065efe25605c1ac82a441dbf8', TRUE, NOW() - INTERVAL 2 HOUR, '10.10.1.10'),
(21, 2, 21, 'camila.rocha@enfil.com.br', 'scrypt:32768:8:1$NMXQmJ4GCOJVmNoe$c62100d1b8d581dddc096ec887df55f1a716ab08c8cbd8f6ff16eae875822597681b6b29e4633ef098f281d3b7ab47c7b8540be065efe25605c1ac82a441dbf8', TRUE, NOW() - INTERVAL 35 MINUTE, '10.10.1.21'),
(22, 2, 22, 'rafael.nunes@enfil.com.br', 'scrypt:32768:8:1$NMXQmJ4GCOJVmNoe$c62100d1b8d581dddc096ec887df55f1a716ab08c8cbd8f6ff16eae875822597681b6b29e4633ef098f281d3b7ab47c7b8540be065efe25605c1ac82a441dbf8', TRUE, NOW() - INTERVAL 10 MINUTE, '10.10.2.22'),
(23, 2, 26, 'fiscal@sanecamp.example', 'scrypt:32768:8:1$NMXQmJ4GCOJVmNoe$c62100d1b8d581dddc096ec887df55f1a716ab08c8cbd8f6ff16eae875822597681b6b29e4633ef098f281d3b7ab47c7b8540be065efe25605c1ac82a441dbf8', TRUE, NOW() - INTERVAL 1 DAY, '177.10.20.30');

INSERT INTO usuario_papel (empresa_id, usuario_id, papel_id, ativo) VALUES
(2, 20, 1, TRUE),
(2, 21, 20, TRUE),
(2, 22, 3, TRUE),
(2, 23, 5, TRUE);

-- Obra, frentes e alocacoes
INSERT INTO obras (
    id, empresa_id, nome, data_inicio, data_fim_planejada, usuario_responsavel_id,
    tipo_obra_id, cliente_id, cnpj_obra, logradouro, numero, complemento, bairro,
    cidade, estado, cep, hora_entrada_padrao, intervalo_entrada_padrao,
    intervalo_saida_padrao, hora_saida_padrao, ativo, criado_por
) VALUES
(20, 2, 'Ampliacao ETE Capivari II', '2026-01-08', '2027-04-30', 22, 20, 20,
 '07.123.456/0042-18', 'Estrada Municipal do Capivari', '4500', 'Area operacional 2',
 'Distrito Industrial', 'Campinas', 'SP', '13064-900', '07:00:00', '12:00:00',
 '13:00:00', '17:00:00', TRUE, 21);

INSERT INTO obra_config (empresa_id, obra_id, chave, valor) VALUES
(2, 20, 'workflow.aprovacao.ordem', '["ENGENHEIRO_RESIDENTE","GESTOR_CONTRATO","FISCAL_CLIENTE"]'),
(2, 20, 'workflow.aprovacao.sla_horas', '12'),
(2, 20, 'rdo.secoes.fotos', 'true'),
(2, 20, 'rdo.secoes.ocorrencias', 'true');

INSERT INTO frente_trabalho (id, empresa_id, obra_id, nome, centro_custo, data_inicio, data_fim_planejada, ativo, criado_por) VALUES
(20, 2, 20, 'Linha de recalque norte', 'ETE-CAP2-LR-N', '2026-01-08', '2026-08-15', TRUE, 22),
(21, 2, 20, 'Casa de bombas e tratamento preliminar', 'ETE-CAP2-CB-TP', '2026-02-01', '2026-11-30', TRUE, 22);

INSERT INTO obra_usuario (id, empresa_id, obra_id, usuario_id, papel_id, ativo, criado_por) VALUES
(20, 2, 20, 21, 20, TRUE, 20),
(21, 2, 20, 22, 3, TRUE, 21),
(22, 2, 20, 23, 5, TRUE, 21);

INSERT INTO frente_colaborador (id, empresa_id, frente_id, colaborador_id, funcao_id, data_inicio, ativo, criado_por) VALUES
(20, 2, 20, 22, 1, '2026-01-08', TRUE, 21),
(21, 2, 20, 23, 11, '2026-01-08', TRUE, 21),
(22, 2, 20, 24, 10, '2026-01-10', TRUE, 22),
(23, 2, 20, 25, 21, '2026-01-15', TRUE, 22),
(24, 2, 21, 26, NULL, '2026-02-01', TRUE, 21);

-- Workflow de aprovacao
INSERT INTO workflow_definicoes (id, empresa_id, obra_id, nome, descricao, aprovacao_paralela, rejeicao_cancela_fluxo, sla_horas, ativo, criado_por) VALUES
(20, 2, 20, 'Workflow RDO ETE Capivari II', 'Fluxo sequencial para aprovacao de RDO com validacao interna e fiscalizacao do cliente.', FALSE, TRUE, 12, TRUE, 21);

INSERT INTO workflow_etapas (id, empresa_id, workflow_id, nivel, nome, papel_id, usuario_aprovador_id, obrigatorio, sla_horas, ativo, criado_por) VALUES
(20, 2, 20, 1, 'Validacao do engenheiro residente', 3, 22, TRUE, 4, TRUE, 21),
(21, 2, 20, 2, 'Aprovacao do gestor de contrato', 20, 21, TRUE, 6, TRUE, 21),
(22, 2, 20, 3, 'Assinatura da fiscalizacao do cliente', 5, 23, TRUE, 12, TRUE, 21);

-- RDOs e detalhes operacionais
INSERT INTO rdo (
    id, empresa_id, obra_id, frente_trabalho_id, data_rdo, status, versao,
    bloqueado_em, bloqueado_por, clima_manha_id, clima_tarde_id, hora_entrada,
    hora_saida, intervalo_entrada, intervalo_saida, observacoes, ativo, criado_por
) VALUES
(20, 2, 20, 20, '2026-05-08', 'APROVADO', 1, '2026-05-08 18:40:00', 21, 20, 1, '07:00:00', '17:00:00', '12:00:00', '13:00:00', 'Execucao de escavacao da vala e preparacao de leito para assentamento de tubulacao PEAD DN400.', TRUE, 22),
(21, 2, 20, 21, '2026-05-09', 'PENDENTE', 1, NULL, NULL, 21, 21, '07:00:00', '16:30:00', '12:00:00', '13:00:00', 'Atividades reduzidas por chuva intermitente e aguardando liberacao de area energizada.', TRUE, 22);

INSERT INTO rdo_mao_obra (id, empresa_id, rdo_id, colaborador_id, funcao, quantidade_horas, tipo_mao_obra, observacao, ativo, criado_por) VALUES
(20, 2, 20, 22, 'Engenheiro Residente', 8.00, 'PROPRIA', 'Acompanhamento de campo e liberacao tecnica.', TRUE, 22),
(21, 2, 20, 24, 'Operador de Escavadeira', 8.00, 'TERCEIRO', 'Operacao de escavadeira na frente norte.', TRUE, 22),
(22, 2, 20, 25, 'Soldador PEAD', 6.50, 'TERCEIRO', 'Preparacao de junta e solda por termofusao.', TRUE, 22),
(23, 2, 21, 23, 'Tecnica de Seguranca', 6.00, 'PROPRIA', 'DDS, APR e bloqueio de area.', TRUE, 22);

INSERT INTO rdo_equipamentos (id, empresa_id, rdo_id, equipamento_id, quantidade, horas_utilizadas, status, motivo_parada, ativo, criado_por) VALUES
(20, 2, 20, 20, 1, 7.25, 'OPERANDO', NULL, TRUE, 22),
(21, 2, 20, 22, 2, 5.00, 'OPERANDO', NULL, TRUE, 22),
(22, 2, 21, 21, 1, 2.00, 'PARADO', 'Aguardando liberacao da area de carga.', TRUE, 22);

INSERT INTO rdo_atividades (id, empresa_id, rdo_id, descricao, status, ativo, criado_por) VALUES
(20, 2, 20, 'Escavacao mecanizada de 84 metros lineares de vala para linha de recalque.', 'Concluido', TRUE, 22),
(21, 2, 20, 'Regularizacao de fundo de vala e lancamento de lastro de areia.', 'Concluido', TRUE, 22),
(22, 2, 21, 'Montagem preliminar da casa de bombas.', 'Em Andamento', TRUE, 22);

INSERT INTO rdo_ocorrencias (id, empresa_id, rdo_id, tipo_ocorrencia, descricao, impacto, tempo_paralisacao, ativo, criado_por) VALUES
(20, 2, 20, 20, 'Identificada interferencia de rede pluvial nao cadastrada no trecho 03.', 'MEDIO', 1.50, TRUE, 22),
(21, 2, 21, 21, 'Servico em area energizada aguardando liberacao formal da concessionaria.', 'ALTO', 3.00, TRUE, 22);

INSERT INTO rdo_fotos (id, empresa_id, rdo_id, arquivo, comentario, ativo, criado_por) VALUES
(20, 2, 20, '/static/uploads/rdo/20/vala_trecho_03.jpg', 'Vala escavada no trecho 03 com sinalizacao lateral.', TRUE, 22),
(21, 2, 20, '/static/uploads/rdo/20/solda_pead_dn400.jpg', 'Solda PEAD DN400 registrada antes do ensaio visual.', TRUE, 22),
(22, 2, 21, '/static/uploads/rdo/21/casa_bombas_base.jpg', 'Base da casa de bombas apos chuva.', TRUE, 22);

INSERT INTO rdo_aprovacoes (id, empresa_id, rdo_id, aprovador_id, nivel, status, data_aprovacao, comentario, endereco_ip, hash, imagem_assinatura, ativo, criado_por) VALUES
(20, 2, 20, 22, 1, 'APROVADO', '2026-05-08 17:45:00', 'RDO conferido em campo.', '10.10.2.22', SHA2('rdo-20-nivel-1', 256), NULL, TRUE, 22),
(21, 2, 20, 21, 2, 'APROVADO', '2026-05-08 18:20:00', 'Aprovado para envio ao cliente.', '10.10.1.21', SHA2('rdo-20-nivel-2', 256), NULL, TRUE, 21),
(22, 2, 20, 23, 3, 'APROVADO', '2026-05-08 18:40:00', 'Fiscalizacao aprova o diario.', '177.10.20.30', SHA2('rdo-20-nivel-3', 256), NULL, TRUE, 23),
(23, 2, 21, 21, 1, 'PENDENTE', NULL, NULL, NULL, NULL, NULL, TRUE, 22);

INSERT INTO rdo_assinaturas (id, empresa_id, rdo_id, usuario_id, colaborador_id, tipo_assinatura, status, hash_documento, ip, user_agent, assinado_em) VALUES
(20, 2, 20, 21, 21, 'INTERNO', 'ASSINADO', SHA2('assinatura-rdo-20-camila', 256), '10.10.1.21', 'Mozilla/5.0 RDO Seed', '2026-05-08 18:20:00'),
(21, 2, 20, 23, 26, 'CLIENTE', 'ASSINADO', SHA2('assinatura-rdo-20-cliente', 256), '177.10.20.30', 'Mozilla/5.0 RDO Seed', '2026-05-08 18:40:00');

INSERT INTO rdo_versoes (id, empresa_id, rdo_id, numero_versao, motivo, dados_snapshot, hash_snapshot, criado_por, criado_em) VALUES
(20, 2, 20, 1, 'Snapshot automatico no bloqueio por aprovacao final',
 JSON_OBJECT('rdo_id', 20, 'status', 'APROVADO', 'obra_id', 20, 'data_rdo', '2026-05-08', 'versao', 1),
 SHA2('snapshot-rdo-20-v1', 256), 21, '2026-05-08 18:40:00');

-- Arquivos, notificacoes, sessoes e auditoria
INSERT INTO arquivos (id, empresa_id, obra_id, rdo_id, entidade, entidade_id, categoria, nome_original, nome_armazenado, mime_type, tamanho_bytes, storage_provider, storage_path, hash_arquivo, publico, ativo, criado_por) VALUES
(20, 2, 20, NULL, 'obras', 20, 'CONTRATO', 'Contrato_SANECAMP_ETE_Capivari_II.pdf', 'contrato_sanecamp_ete_capivari_ii.pdf', 'application/pdf', 2457600, 'LOCAL', '/static/uploads/obras/20/contrato_sanecamp_ete_capivari_ii.pdf', SHA2('contrato-capivari-ii', 256), FALSE, TRUE, 21),
(21, 2, 20, 20, 'rdo', 20, 'PDF', 'RDO_0001_2026-05-08.pdf', 'rdo_20_v1.pdf', 'application/pdf', 524288, 'LOCAL', '/static/uploads/rdo/20/rdo_20_v1.pdf', SHA2('pdf-rdo-20-v1', 256), TRUE, TRUE, 22),
(22, 2, 20, 20, 'rdo_fotos', 20, 'IMAGEM', 'vala_trecho_03.jpg', 'vala_trecho_03.jpg', 'image/jpeg', 384120, 'LOCAL', '/static/uploads/rdo/20/vala_trecho_03.jpg', SHA2('foto-vala-trecho-03', 256), FALSE, TRUE, 22);

INSERT INTO notificacoes (id, empresa_id, usuario_id, obra_id, rdo_id, tipo, titulo, mensagem, link, lida, lida_em, ativo, criado_por, criado_em) VALUES
(20, 2, 21, 20, 21, 'APROVACAO_PENDENTE', 'RDO pendente de aprovacao', 'O RDO de 2026-05-09 aguarda aprovacao do gestor de contrato.', 'auth/visualizar-rdo/21', FALSE, NULL, TRUE, 22, NOW()),
(21, 2, 23, 20, 20, 'NOVO_RDO', 'RDO aprovado disponivel', 'O RDO de 2026-05-08 foi aprovado e esta disponivel para consulta.', 'auth/visualizar-rdo/20', TRUE, NOW() - INTERVAL 1 HOUR, TRUE, 21, NOW() - INTERVAL 2 HOUR),
(22, 2, 22, 20, 21, 'ALERTA', 'Liberacao de area pendente', 'Aguardando liberacao da concessionaria para continuidade dos servicos.', 'auth/visualizar-rdo/21', FALSE, NULL, TRUE, 23, NOW());

INSERT INTO sessoes_usuario (id, empresa_id, usuario_id, token_hash, ip, user_agent, iniciada_em, expira_em, encerrada_em, encerrada_por, motivo_encerramento, ativa) VALUES
(20, 2, 21, SHA2('sessao-camila-ativa', 256), '10.10.1.21', 'Mozilla/5.0 RDO Seed', NOW() - INTERVAL 35 MINUTE, NOW() + INTERVAL 565 MINUTE, NULL, NULL, NULL, TRUE),
(21, 2, 22, SHA2('sessao-rafael-encerrada', 256), '10.10.2.22', 'Mozilla/5.0 RDO Seed', NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY, 22, 'SESSAO_EXPIRADA', FALSE);

INSERT INTO acesso_log (id, empresa_id, usuario_id, email, acao, ip, user_agent, detalhes, criado_em) VALUES
(20, 2, 21, 'camila.rocha@enfil.com.br', 'LOGIN_SUCESSO', '10.10.1.21', 'Mozilla/5.0 RDO Seed', JSON_OBJECT('origem', 'seed', 'mfa', true), NOW() - INTERVAL 35 MINUTE),
(21, 2, 22, 'rafael.nunes@enfil.com.br', 'LOGOUT', '10.10.2.22', 'Mozilla/5.0 RDO Seed', JSON_OBJECT('origem', 'seed'), NOW() - INTERVAL 1 DAY),
(22, 2, NULL, 'tentativa.invalida@enfil.com.br', 'LOGIN_FALHA', '200.10.10.10', 'Mozilla/5.0 RDO Seed', JSON_OBJECT('motivo', 'senha_invalida'), NOW() - INTERVAL 3 HOUR);

INSERT INTO auditoria_log (id, empresa_id, usuario_id, colaborador_id, acao, entidade, entidade_id, dados_antes, dados_depois, ip, user_agent, criado_em) VALUES
(20, 2, 22, 22, 'CREATE', 'rdo', 20, NULL, JSON_OBJECT('status', 'PENDENTE', 'obra_id', 20, 'data_rdo', '2026-05-08'), '10.10.2.22', 'Mozilla/5.0 RDO Seed', '2026-05-08 17:10:00'),
(21, 2, 21, 21, 'APPROVE', 'rdo', 20, JSON_OBJECT('status', 'PENDENTE'), JSON_OBJECT('status', 'APROVADO'), '10.10.1.21', 'Mozilla/5.0 RDO Seed', '2026-05-08 18:20:00'),
(22, 2, 23, 26, 'SIGN', 'rdo_assinaturas', 21, JSON_OBJECT('status', 'PENDENTE'), JSON_OBJECT('status', 'ASSINADO'), '177.10.20.30', 'Mozilla/5.0 RDO Seed', '2026-05-08 18:40:00');

SET FOREIGN_KEY_CHECKS = 1;