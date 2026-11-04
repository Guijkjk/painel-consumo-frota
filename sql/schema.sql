-- Somente estrutura. Nenhum dado operacional.
CREATE DATABASE IF NOT EXISTS gestao_frota
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE gestao_frota;

CREATE TABLE IF NOT EXISTS veiculos (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  prefixo VARCHAR(30) NOT NULL UNIQUE,
  modelo VARCHAR(100),
  ativo BOOLEAN NOT NULL DEFAULT TRUE,
  criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS importacoes (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nome_arquivo VARCHAR(255) NOT NULL,
  arquivo_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
  quantidade_registros INT UNSIGNED NOT NULL,
  importado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS abastecimentos (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  veiculo_id BIGINT UNSIGNED NOT NULL,
  importacao_id BIGINT UNSIGNED NOT NULL,
  data_referencia DATE NOT NULL,
  hora TIME NOT NULL,
  bomba VARCHAR(30) NOT NULL,
  litros DECIMAL(14,3) NOT NULL,
  km_total DECIMAL(14,2) NOT NULL,
  km_litro_informado DECIMAL(10,2) NOT NULL,
  observacoes TEXT,
  pagina_pdf INT UNSIGNED NOT NULL,
  criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (veiculo_id) REFERENCES veiculos(id),
  FOREIGN KEY (importacao_id) REFERENCES importacoes(id),
  INDEX idx_veiculo_data (veiculo_id,data_referencia),
  INDEX idx_data (data_referencia)
) ENGINE=InnoDB;
