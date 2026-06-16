CREATE TABLE aux_tipo_equipamento (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  nome VARCHAR(100) NOT NULL,
  ativo BOOLEAN NOT NULL DEFAULT TRUE,
  is_system BOOLEAN NOT NULL DEFAULT FALSE,
  criado_por INTEGER NULL,
  modificado_por INTEGER NULL,
  criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
  modificado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_aux_tipo_equipamento_nome UNIQUE (nome)
);

CREATE INDEX ix_aux_tipo_equipamento_nome ON aux_tipo_equipamento (nome);
CREATE INDEX ix_aux_tipo_equipamento_ativo ON aux_tipo_equipamento (ativo);

INSERT INTO aux_tipo_equipamento (nome, ativo, is_system, criado_em, modificado_em)
SELECT DISTINCT TRIM(tipo), TRUE, FALSE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM aux_equipamentos
WHERE tipo IS NOT NULL AND TRIM(tipo) <> '';

INSERT IGNORE INTO aux_tipo_equipamento (nome, ativo, is_system, criado_em, modificado_em) VALUES
('Acesso e Andaimes', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Bombeamento e Drenagem', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Compactação', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Concretagem', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Corte e Demolição', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Escavação e Terraplenagem', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Ferramentas Elétricas', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Ferramentas Manuais', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Fundação', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Geração de Energia', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Içamento e Elevação', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Limpeza e Acabamento', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Movimentação de Cargas', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Pavimentação', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Perfuração', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Solda e Corte Térmico', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Topografia e Medição', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Transporte', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Segurança e Sinalização', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Não informado', TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

ALTER TABLE aux_equipamentos ADD COLUMN tipo_id INTEGER NULL;

UPDATE aux_equipamentos e
SET tipo_id = (
  SELECT t.id
  FROM aux_tipo_equipamento t
  WHERE t.nome = COALESCE(NULLIF(TRIM(e.tipo), ''), 'Não informado')
  LIMIT 1
);

ALTER TABLE aux_equipamentos MODIFY tipo_id INTEGER NOT NULL;

ALTER TABLE aux_equipamentos
  ADD CONSTRAINT fk_aux_equipamentos_tipo_id_aux_tipo_equipamento
  FOREIGN KEY (tipo_id) REFERENCES aux_tipo_equipamento(id);

CREATE INDEX ix_aux_equipamentos_tipo_id ON aux_equipamentos (tipo_id);

ALTER TABLE aux_equipamentos DROP COLUMN tipo;
