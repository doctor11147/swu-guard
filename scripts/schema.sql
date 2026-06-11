-- =============================================================================
-- 西南大学校园人脸识别门禁系统 · MySQL 9.x 数据模型
-- =============================================================================
-- 版本     : v2.1（当前完整基线；对齐 ORM 与 0001-0006 迁移链）
-- 引擎     : InnoDB
-- 字符集   : utf8mb4 / utf8mb4_0900_ai_ci
-- 时间精度 : DATETIME(3)（毫秒）
-- 时区约定 : 应用层统一以 Asia/Shanghai 写入；表内仅存 naive datetime
-- 命名规范 : 表名复数 snake_case；列名 snake_case；外键 fk_<from>_<to>
-- 软删除   : 仅 persons 启用（deleted_at IS NULL 即有效）
-- 表数量   : 12 张业务表（含 admin_gate_permissions 关联表）
-- -----------------------------------------------------------------------------
-- 学校信息（来源 swu-context.md §一）
--   全称 : 西南大学  |  英文 : Southwest University (SWU)
--   国标码: 10635   |  ICP : 渝ICP 06005063号-4
--   主校区: 北碚校区·重庆市北碚区天生路2号·400715
--   校训 : 含弘光大，继往开来   大学精神 : 特立西南，学行天下
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `face_gate`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `face_gate`;

-- 表创建顺序：先无依赖、后依赖；删除时反向。

-- -----------------------------------------------------------------------------
-- 1. faculties: 学部（一级单位）— 数据来源 swu-context.md §四
--    11 个常规学部 + 1 个中外合作办学分类 = 12 行
-- -----------------------------------------------------------------------------
CREATE TABLE `faculties` (
  `id`              SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `code`            VARCHAR(32)     NOT NULL                COMMENT '学部代码，如 faculty_math_info',
  `name`            VARCHAR(64)     NOT NULL                COMMENT '中文全称，如 数学与信息科学学部',
  `is_active`       TINYINT(1)      NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_faculties_code` (`code`),
  UNIQUE KEY `uq_faculties_name` (`name`)
) ENGINE=InnoDB COMMENT='西南大学学部（一级单位）';

-- -----------------------------------------------------------------------------
-- 2. colleges: 学院/系（二级单位）— 数据来源 swu-context.md §四
--    每个 college 归属一个 faculty。
-- -----------------------------------------------------------------------------
CREATE TABLE `colleges` (
  `id`              SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `faculty_id`      SMALLINT UNSIGNED NULL                  COMMENT 'FK faculties.id',
  `code`            VARCHAR(16)     NOT NULL                COMMENT '学院代码（学号 7-9 位语义；非学院的研究所给占位）',
  `name`            VARCHAR(128)    NOT NULL                COMMENT '学院全称',
  `short_name`      VARCHAR(32)     NULL                    COMMENT '简称',
  `is_active`       TINYINT(1)      NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_colleges_code` (`code`),
  UNIQUE KEY `uq_colleges_name` (`name`),
  KEY `ix_colleges_faculty` (`faculty_id`),
  CONSTRAINT `fk_colleges_faculty`
    FOREIGN KEY (`faculty_id`) REFERENCES `faculties`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB COMMENT='西南大学学院/研究所（二级单位）';

-- -----------------------------------------------------------------------------
-- 3. admins: 管理员账户（登录系统的人）
-- -----------------------------------------------------------------------------
CREATE TABLE `admins` (
  `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username`        VARCHAR(64)     NOT NULL,
  `password_hash`   VARCHAR(255)    NOT NULL                COMMENT 'bcrypt $2b$...',
  `name`            VARCHAR(128)    NOT NULL,
  `email`           VARCHAR(128)    NULL,
  `role`            ENUM('superadmin','admin','guard','viewer') NOT NULL DEFAULT 'admin'
                                                            COMMENT 'guard=门卫；仅看自己门相关数据',
  `is_active`       TINYINT(1)      NOT NULL DEFAULT 1,
  `last_login_at`   DATETIME(3)     NULL,
  `created_at`      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_admins_username` (`username`)
) ENGINE=InnoDB COMMENT='管理员账户';

-- -----------------------------------------------------------------------------
-- 4. persons: 已注册人员（本科生 / 研究生 / 教师 / 职工 / 访客）
--
-- 学号格式（西南大学）：本科生 15 位
--   1-2 = 学生类型(22) | 3-6 = 入学年份(2022) | 7-9 = 学院代码(326)
--   10-12 = 班级编号(062)   | 13-15 = 班内序号(003)
-- 例：222022326062999
--
-- 设计：persons.college_id FK 保证引用完整性；同时**冗余存** faculty_name /
-- school_name 文本副本，便于 CSV 导入兜底（学院找不到时仍可入库），并加速大屏
-- 聚合查询。两者由 service 层在写入时同步。
-- -----------------------------------------------------------------------------
CREATE TABLE `persons` (
  `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `external_id`     VARCHAR(32)     NOT NULL                COMMENT '学号（本科 15 位）/ 研究生学号 / 教工号',
  `name`            VARCHAR(128)    NOT NULL,
  `role`            ENUM('student','graduate','teacher','staff','visitor') NOT NULL DEFAULT 'student'
                                                            COMMENT '本科生/研究生/教师/职工/访客',
  `college_id`      SMALLINT UNSIGNED NULL                  COMMENT 'FK colleges.id（首选关联）',
  `faculty_name`    VARCHAR(64)     NULL                    COMMENT '冗余：学部名（CSV 导入兜底/聚合加速）',
  `school_name`     VARCHAR(128)    NULL                    COMMENT '冗余：学院名',
  `major`           VARCHAR(128)    NULL                    COMMENT '专业，如 计算机科学与技术',
  `class_code`      VARCHAR(64)     NULL                    COMMENT '班级，如 2022级06班',
  `enrollment_year` SMALLINT UNSIGNED NULL                  COMMENT '入学年份（学生）/ 入职年份（教职工）',
  `campus`          ENUM('beibei','rongchang') NOT NULL DEFAULT 'beibei'
                                                            COMMENT '所属校区',
  `dorm_zone`       ENUM('nan','zhu','mei','li','ju','tao','xing') NULL
                                                            COMMENT '宿舍园区：楠/竹/梅/李/橘/桃/杏',
  `phone`           VARCHAR(32)     NULL,
  `email`           VARCHAR(128)    NULL,
  `status`          ENUM('active','suspended','graduated','expired') NOT NULL DEFAULT 'active',
  `note`            TEXT            NULL,
  `created_at`      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  `deleted_at`      DATETIME(3)     NULL                    COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_persons_external_id` (`external_id`),
  KEY `ix_persons_status` (`status`),
  KEY `ix_persons_role` (`role`),
  KEY `ix_persons_college` (`college_id`),
  KEY `ix_persons_campus` (`campus`),
  KEY `ix_persons_deleted_at` (`deleted_at`),
  CONSTRAINT `fk_persons_college`
    FOREIGN KEY (`college_id`) REFERENCES `colleges`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB COMMENT='已注册人员';

-- -----------------------------------------------------------------------------
-- 5. face_embeddings: 人脸特征向量元数据
--    实际向量存 FAISS 文件 faces.faiss（id 与本表 id 一一对应）
-- -----------------------------------------------------------------------------
CREATE TABLE `face_embeddings` (
  `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT
                                                            COMMENT '同时是 FAISS 向量 id，绝不可重置',
  `person_id`       BIGINT UNSIGNED NOT NULL,
  `sha256`          CHAR(64)        NOT NULL                COMMENT '原图字节 SHA-256，用于去重',
  `image_path`      VARCHAR(512)    NULL                    COMMENT '相对 data/faces/ 的路径',
  `vector_dim`      SMALLINT UNSIGNED NOT NULL DEFAULT 512,
  `model_name`      VARCHAR(64)     NOT NULL                COMMENT '生成此向量的嵌入模型，如 edgeface_s_gamma_05',
  `quality_score`   FLOAT           NULL                    COMMENT '可选：质量评估分数',
  `created_at`      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_face_embeddings_person_sha` (`person_id`, `sha256`),
  KEY `ix_face_embeddings_person_id` (`person_id`),
  CONSTRAINT `fk_face_embeddings_person`
    FOREIGN KEY (`person_id`) REFERENCES `persons`(`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB COMMENT='人脸嵌入元数据（向量本身在 FAISS 中）';

-- -----------------------------------------------------------------------------
-- 6. gates: 门禁点（北碚校区七门 + 荣昌校区扩展）
-- -----------------------------------------------------------------------------
CREATE TABLE `gates` (
  `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `code`            VARCHAR(32)     NOT NULL                COMMENT '门禁编码，如 gate_hanhong',
  `name`            VARCHAR(128)    NOT NULL                COMMENT '展示名，如 含弘门（1号门）',
  `campus`          ENUM('beibei','rongchang') NOT NULL DEFAULT 'beibei',
  `location`        VARCHAR(255)    NULL                    COMMENT '位置描述，如 北碚校区北区入口·行署楼方向',
  `direction`       ENUM('in','out','both') NOT NULL DEFAULT 'both'
                                                            COMMENT '通行方向：仅入/仅出/双向',
  `ip_address`      VARCHAR(64)     NULL,
  `status`          ENUM('online','offline','disabled') NOT NULL DEFAULT 'offline',
  `note`            TEXT            NULL,
  `created_at`      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_gates_code` (`code`),
  KEY `ix_gates_status` (`status`),
  KEY `ix_gates_campus` (`campus`)
) ENGINE=InnoDB COMMENT='门禁点';

-- -----------------------------------------------------------------------------
-- 7. visitor_appointments: 访客预约（自助提交 → 审批 → 有效期内刷脸）
-- -----------------------------------------------------------------------------
CREATE TABLE `visitor_appointments` (
  `id`                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `person_id`         BIGINT UNSIGNED NOT NULL                COMMENT 'FK persons.id（role 必须为 visitor）',
  `id_card`           VARCHAR(32)     NOT NULL                COMMENT '冗余：访客身份证号',
  `visitor_name`      VARCHAR(128)    NOT NULL                COMMENT '冗余：访客姓名',
  `visit_reason`      VARCHAR(512)    NOT NULL                COMMENT '来访原因',
  `arrival_slot`      SMALLINT UNSIGNED NOT NULL              COMMENT '到达时间段 0-5，每段 4 小时',
  `departure_slot`    SMALLINT UNSIGNED NOT NULL              COMMENT '离开时间段 0-5',
  `appointment_date`  DATE            NOT NULL                COMMENT '兼容字段：到达日期',
  `arrival_date`      DATE            NOT NULL                COMMENT '到达日期',
  `departure_date`    DATE            NOT NULL                COMMENT '离开日期',
  `status`            ENUM('pending','approved','rejected','expired','cancelled') NOT NULL DEFAULT 'pending'
                                                              COMMENT '待审批/已通过/已拒绝/已过期/已取消',
  `reviewed_by`       BIGINT UNSIGNED NULL                    COMMENT '审批人 admins.id',
  `reviewed_at`       DATETIME(3)     NULL,
  `reject_reason`     VARCHAR(512)    NULL,
  `created_at`        DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`        DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `ix_va_person_date` (`person_id`, `appointment_date`),
  KEY `ix_va_status` (`status`),
  KEY `ix_va_date_status` (`appointment_date`, `status`),
  KEY `ix_va_id_card` (`id_card`),
  KEY `ix_va_expire_scan` (`status`, `departure_date`, `departure_slot`),
  KEY `ix_va_valid_lookup` (`person_id`, `status`, `arrival_date`, `departure_date`, `arrival_slot`, `departure_slot`),
  KEY `ix_va_window` (`person_id`, `arrival_date`, `departure_date`, `status`),
  CONSTRAINT `fk_appointment_person`
    FOREIGN KEY (`person_id`) REFERENCES `persons`(`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_appointment_reviewer`
    FOREIGN KEY (`reviewed_by`) REFERENCES `admins`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `ck_va_arrival_slot_range` CHECK (`arrival_slot` BETWEEN 0 AND 5),
  CONSTRAINT `ck_va_departure_slot_range` CHECK (`departure_slot` BETWEEN 0 AND 5),
  CONSTRAINT `ck_va_departure_after_arrival`
    CHECK (`departure_date` > `arrival_date` OR (`departure_date` = `arrival_date` AND `departure_slot` >= `arrival_slot`))
) ENGINE=InnoDB COMMENT='访客预约记录';

-- -----------------------------------------------------------------------------
-- 8. access_logs: 通行/识别日志（追加写）
-- -----------------------------------------------------------------------------
CREATE TABLE `access_logs` (
  `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `ts`              DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `gate_id`         BIGINT UNSIGNED NULL,
  `matched_person_id` BIGINT UNSIGNED NULL,
  `visitor_appointment_id` BIGINT UNSIGNED NULL              COMMENT '访客通行时关联的有效预约 id',
  `score`           FLOAT           NULL                    COMMENT '余弦相似度（[-1,1]）',
  `spoof_score`     FLOAT           NULL                    COMMENT '活体真实度（[0,1]）',
  `decision`        ENUM('granted','rejected','spoof','no_face') NOT NULL,
  `snapshot_path`   VARCHAR(512)    NULL                    COMMENT '现场抓拍路径（可选）',
  `detail`          TEXT            NULL,
  `adaptive_profile` VARCHAR(32)    NULL                    COMMENT '生效的 adaptive profile',
  `adaptive_reason` VARCHAR(1024)   NULL                    COMMENT '自适应策略原因',
  `runtime_thresholds` JSON         NULL                    COMMENT '识别时生效的阈值快照',
  PRIMARY KEY (`id`),
  KEY `ix_access_logs_ts` (`ts`),
  KEY `ix_access_logs_decision_ts` (`decision`, `ts`),
  KEY `ix_access_logs_person_ts` (`matched_person_id`, `ts`),
  KEY `ix_access_logs_gate_ts` (`gate_id`, `ts`),
  KEY `ix_access_logs_visitor_appointment` (`visitor_appointment_id`),
  CONSTRAINT `fk_access_logs_person`
    FOREIGN KEY (`matched_person_id`) REFERENCES `persons`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_access_logs_gate`
    FOREIGN KEY (`gate_id`) REFERENCES `gates`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_access_logs_visitor_appointment`
    FOREIGN KEY (`visitor_appointment_id`) REFERENCES `visitor_appointments`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB COMMENT='通行/识别日志';

-- -----------------------------------------------------------------------------
-- 9. admin_gate_permissions: 门卫 ↔ 所管辖门 多对多
--     仅当 admins.role='guard' 时有意义。admin / superadmin 跳过该表（全权限）。
-- -----------------------------------------------------------------------------
CREATE TABLE `admin_gate_permissions` (
  `admin_id` BIGINT UNSIGNED NOT NULL,
  `gate_id`  BIGINT UNSIGNED NOT NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`admin_id`, `gate_id`),
  KEY `ix_agp_gate` (`gate_id`),
  CONSTRAINT `fk_agp_admin` FOREIGN KEY (`admin_id`) REFERENCES `admins`(`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_agp_gate`  FOREIGN KEY (`gate_id`)  REFERENCES `gates`(`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB COMMENT='门卫 ↔ 所管辖门（多对多）';

-- -----------------------------------------------------------------------------
-- 10. environment_snapshots: 环境感知快照（VLM / 规则 / 天气融合）
-- -----------------------------------------------------------------------------
CREATE TABLE `environment_snapshots` (
  `id`                      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `gate_id`                 BIGINT UNSIGNED NULL,
  `provider`                VARCHAR(32)     NOT NULL DEFAULT 'rule',
  `location_name`           VARCHAR(128)    NULL,
  `scene_tag`               VARCHAR(64)     NULL,
  `lighting_quality`        VARCHAR(32)     NULL,
  `weather_text`            VARCHAR(128)    NULL,
  `cloud_pct`               FLOAT           NULL,
  `visibility_km`           FLOAT           NULL,
  `precipitation_mm`        FLOAT           NULL,
  `irradiance`              FLOAT           NULL,
  `humidity_pct`            FLOAT           NULL,
  `is_day`                  TINYINT(1)      NULL,
  `camera_luma_mean`        FLOAT           NULL,
  `camera_luma_std`         FLOAT           NULL,
  `camera_blur_score`       FLOAT           NULL,
  `under_exposed_ratio`     FLOAT           NULL,
  `over_exposed_ratio`      FLOAT           NULL,
  `recent_reject_rate`      FLOAT           NULL,
  `recent_low_quality_rate` FLOAT           NULL,
  `recent_spoof_reject_rate` FLOAT          NULL,
  `recent_avg_similarity`   FLOAT           NULL,
  `vlm_raw_json`            JSON            NULL,
  `weather_raw_json`        JSON            NULL,
  `created_at`              DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `ix_env_gate_time` (`gate_id`, `created_at`),
  KEY `ix_env_created_at` (`created_at`)
) ENGINE=InnoDB COMMENT='环境感知快照';

-- -----------------------------------------------------------------------------
-- 11. adaptive_policy_logs: 自适应策略审计日志
-- -----------------------------------------------------------------------------
CREATE TABLE `adaptive_policy_logs` (
  `id`               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `snapshot_id`      BIGINT UNSIGNED NULL,
  `gate_id`          BIGINT UNSIGNED NULL,
  `source`           ENUM('rule_only','vlm','vlm_weather','manual') NOT NULL DEFAULT 'rule_only',
  `profile`          VARCHAR(32)     NOT NULL,
  `risk_level`       ENUM('low','medium','high','critical') NOT NULL,
  `action_tags`      JSON            NOT NULL,
  `llm_output`       JSON            NULL,
  `validated_config` JSON            NOT NULL,
  `applied`          TINYINT(1)      NOT NULL DEFAULT 0,
  `reason`           VARCHAR(1024)   NULL,
  `created_at`       DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `ix_policy_gate_time` (`gate_id`, `created_at`),
  KEY `ix_policy_profile_time` (`profile`, `created_at`),
  CONSTRAINT `fk_policy_snapshot`
    FOREIGN KEY (`snapshot_id`) REFERENCES `environment_snapshots`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB COMMENT='自适应策略审计日志';

-- -----------------------------------------------------------------------------
-- 12. system_configs: 全局可调参数（KV + JSON）
-- -----------------------------------------------------------------------------
CREATE TABLE `system_configs` (
  `config_key`      VARCHAR(64)     NOT NULL,
  `value_json`      JSON            NOT NULL,
  `description`     VARCHAR(255)    NULL,
  `updated_by`      BIGINT UNSIGNED NULL,
  `updated_at`      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`config_key`),
  CONSTRAINT `fk_system_configs_admin`
    FOREIGN KEY (`updated_by`) REFERENCES `admins`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB COMMENT='全局系统配置 KV 存储';

-- =============================================================================
-- 种子数据（idempotent）
-- =============================================================================

-- ---- 1. 12 个学部分类（含中外合作办学）·按 swu-context.md §四 顺序 ----
INSERT INTO `faculties` (`code`, `name`) VALUES
  ('faculty_humanities',   '人文学部'),
  ('faculty_social_sci',   '社会科学学部'),
  ('faculty_education',    '教育科学学部'),
  ('faculty_arts',         '艺术学部'),
  ('faculty_chem_mat',     '理化与材料学部'),
  ('faculty_resource_env', '资源环境学部'),
  ('faculty_engineering',  '工学部'),
  ('faculty_math_info',    '数学与信息科学学部'),
  ('faculty_agriculture',  '农学部'),
  ('faculty_animal_sci',   '动物科学学部'),
  ('faculty_life_sci',     '生命科学学部'),
  ('faculty_intl',         '中外合作办学')
ON DUPLICATE KEY UPDATE `code`=`code`;

-- ---- 2. 学院（按学部归属，覆盖 swu-context.md §四 全部条目）----
-- 注意：code 选用与本科生学号 7-9 位的"学院代码"语义对齐的 3 位数字（占位，
-- 真实 code 待学校提供后由迁移脚本 UPDATE）。无对应学号代码的研究所留空字符串。
INSERT INTO `colleges` (`faculty_id`, `code`, `name`, `short_name`)
SELECT f.id, t.code, t.name, t.short_name FROM (
  -- faculty_humanities
  SELECT 'faculty_humanities' AS fcode, '103' AS code, '文学院' AS name, '文学院' AS short_name UNION ALL
  SELECT 'faculty_humanities', '104', '外国语学院', '外院' UNION ALL
  SELECT 'faculty_humanities', '105', '历史文化学院 民族学院', '历史学院' UNION ALL
  SELECT 'faculty_humanities', '160', '国际学院', '国院' UNION ALL
  SELECT 'faculty_humanities', '161', '汉语言文献研究所', '汉语所' UNION ALL
  SELECT 'faculty_humanities', '162', '中国新诗研究所', '新诗所' UNION ALL
  -- faculty_social_sci
  SELECT 'faculty_social_sci', '100', '马克思主义学院', '马院' UNION ALL
  SELECT 'faculty_social_sci', '108', '经济管理学院', '经管' UNION ALL
  SELECT 'faculty_social_sci', '109', '国家治理学院', '国治' UNION ALL
  SELECT 'faculty_social_sci', '107', '法学院', '法学院' UNION ALL
  SELECT 'faculty_social_sci', '170', '商贸学院', '商贸' UNION ALL
  SELECT 'faculty_social_sci', '171', '乡村振兴战略研究院', '乡振院' UNION ALL
  -- faculty_education
  SELECT 'faculty_education', '101', '教育学部', '教育学部' UNION ALL
  SELECT 'faculty_education', '102', '心理学部', '心理学部' UNION ALL
  SELECT 'faculty_education', '126', '体育学院', '体院' UNION ALL
  SELECT 'faculty_education', '180', '教师教育学院', '师教院' UNION ALL
  SELECT 'faculty_education', '181', '西南民族教育与心理研究中心', '民教中心' UNION ALL
  -- faculty_arts
  SELECT 'faculty_arts', '127', '音乐学院', '音乐' UNION ALL
  SELECT 'faculty_arts', '128', '美术学院', '美院' UNION ALL
  SELECT 'faculty_arts', '106', '新闻传媒学院', '新传' UNION ALL
  -- faculty_chem_mat
  SELECT 'faculty_chem_mat', '112', '化学化工学院', '化院' UNION ALL
  SELECT 'faculty_chem_mat', '111', '物理科学与技术学院', '物院' UNION ALL
  SELECT 'faculty_chem_mat', '115', '材料与能源学院', '材能' UNION ALL
  -- faculty_resource_env
  SELECT 'faculty_resource_env', '116', '资源环境学院', '资环' UNION ALL
  SELECT 'faculty_resource_env', '114', '地理科学学院', '地科' UNION ALL
  -- faculty_engineering
  SELECT 'faculty_engineering', '117', '工程技术学院', '工程' UNION ALL
  SELECT 'faculty_engineering', '124', '食品科学学院', '食科' UNION ALL
  -- faculty_math_info（用户所属学部，重点）
  SELECT 'faculty_math_info', '110', '数学与统计学院', '数统' UNION ALL
  SELECT 'faculty_math_info', '326', '计算机与信息科学学院 软件学院', '计信院' UNION ALL  -- ★ 用户所在学院
  SELECT 'faculty_math_info', '327', '电子信息工程学院', '电信院' UNION ALL
  SELECT 'faculty_math_info', '200', '人工智能学院', 'AI 学院' UNION ALL
  -- faculty_agriculture
  SELECT 'faculty_agriculture', '122', '农学与生物科技学院', '农学' UNION ALL
  SELECT 'faculty_agriculture', '190', '植物保护学院', '植保' UNION ALL
  SELECT 'faculty_agriculture', '121', '园艺园林学院', '园艺' UNION ALL
  SELECT 'faculty_agriculture', '191', '柑桔研究所', '柑桔所' UNION ALL
  -- faculty_animal_sci
  SELECT 'faculty_animal_sci', '123', '蚕桑纺织与生物质科学学院', '蚕学' UNION ALL
  SELECT 'faculty_animal_sci', '120', '动物科学技术学院', '动科' UNION ALL
  SELECT 'faculty_animal_sci', '195', '动物医学院', '动医' UNION ALL
  SELECT 'faculty_animal_sci', '196', '水产学院', '水产' UNION ALL
  SELECT 'faculty_animal_sci', '197', '资源昆虫高效养殖与利用全国重点实验室', '昆虫实验室' UNION ALL
  -- faculty_life_sci
  SELECT 'faculty_life_sci', '113', '生命科学学院', '生科' UNION ALL
  SELECT 'faculty_life_sci', '125', '药学院 中医药学院', '药学院' UNION ALL
  SELECT 'faculty_life_sci', '198', '前沿交叉学科研究院 生物学研究中心', '前沿院' UNION ALL
  SELECT 'faculty_life_sci', '199', '发育生物学与再生医学研究中心', '发育中心' UNION ALL
  SELECT 'faculty_life_sci', '210', '医学研究院', '医研院' UNION ALL
  -- faculty_intl
  SELECT 'faculty_intl', '300', '西塔学院', '西塔'
) AS t
JOIN `faculties` f ON f.code = t.fcode
ON DUPLICATE KEY UPDATE `colleges`.`code`=`colleges`.`code`;

-- 管理员账户不在公开脚本中预置。初始化后运行：
-- python -m app.scripts.seed_admin --username admin --password "<strong-password>"

-- ---- 4. 北碚校区七门（swu-context.md §三）----
INSERT INTO `gates` (`code`, `name`, `campus`, `location`, `direction`, `status`) VALUES
  ('gate_hanhong',   '含弘门（1号门）',   'beibei', '北碚校区北区入口·行署楼方向',                'both', 'online'),
  ('gate_xuexing',   '学行门（2号门）',   'beibei', '北碚校区南区入口·共青花园方向',              'both', 'online'),
  ('gate_tiansheng', '天生门（3号门）',   'beibei', '北碚校区·中心体育馆、第三运动场方向',        'both', 'offline'),
  ('gate_xuefu',     '学府门（5号门）',   'beibei', '北碚校区北区·桂园宾馆、西师街方向',          'both', 'offline'),
  ('gate_xueyuan',   '学苑门（6号门）',   'beibei', '北碚校区·食品科学学院、植物保护学院方向',    'both', 'offline'),
  ('gate_wenxing',   '文星门（7号门）',   'beibei', '北碚校区·文化与社会发展学院、文学院方向',    'both', 'offline'),
  ('gate_jiangjun',  '将军门（8号门）',   'beibei', '北碚校区·农学与生物科技学院、经管学院方向',  'both', 'offline')
ON DUPLICATE KEY UPDATE `code`=`code`;

-- ---- 5. 系统配置（涵盖学校身份、识别参数、UI 主题）----
INSERT INTO `system_configs` (`config_key`, `value_json`, `description`) VALUES
  -- 学校身份（来源 swu-context.md §一）
  ('school.code',              JSON_OBJECT('value', '10635'),                  '教育部国标码'),
  ('school.name_zh',           JSON_OBJECT('value', '西南大学'),                '学校中文名'),
  ('school.name_en',           JSON_OBJECT('value', 'Southwest University'),    '学校英文名'),
  ('school.url',               JSON_OBJECT('value', 'https://www.swu.edu.cn'), '官网'),
  ('school.icp',               JSON_OBJECT('value', '渝ICP 06005063号-4'),     'ICP 备案号'),
  ('school.motto',             JSON_OBJECT('value', '含弘光大，继往开来'),       '校训'),
  ('school.spirit',            JSON_OBJECT('value', '特立西南，学行天下'),       '大学精神'),
  ('school.founded_year',      JSON_OBJECT('value', 1906),                     '建校年份'),
  ('school.campus_main',       JSON_OBJECT('value', 'beibei'),                  '主校区'),
  ('school.campus_main_addr',  JSON_OBJECT('value', '重庆市北碚区天生路2号'),     '主校区地址'),
  -- 识别参数（与 app/config.yaml 镜像；以本表为准）
  ('recognition.match_threshold',     JSON_OBJECT('value', 0.40),  '1:N 余弦匹配阈值'),
  ('recognition.spoof_threshold',     JSON_OBJECT('value', 0.85),  'MiniFAS 活体真实度阈值'),
  ('recognition.anti_spoof_enabled',  JSON_OBJECT('value', true),  '是否启用活体校验'),
  ('recognition.embedder_model',      JSON_OBJECT('value', 'edgeface_s_gamma_05'), '当前嵌入模型'),
  ('recognition.snapshot_keep_days',  JSON_OBJECT('value', 90),    '通行抓拍保留天数'),
  -- 访客预约
  ('visitor.slot_count',              JSON_OBJECT('value', 6),     '访客预约每日时间段数'),
  ('visitor.slot_duration_h',         JSON_OBJECT('value', 4),     '访客预约单时间段小时数'),
  ('visitor.max_per_slot',            JSON_OBJECT('value', 20),    '访客预约单时段审批容量'),
  ('visitor.auto_expire_min',         JSON_OBJECT('value', 30),    '访客预约过期扫描宽限分钟数'),
  ('visitor.workflow.required_face',  JSON_OBJECT('value', true),  '访客预约前必须已录入人脸'),
  ('visitor.workflow.slot_labels',    JSON_OBJECT('value', JSON_ARRAY('00:00-04:00', '04:00-08:00', '08:00-12:00', '12:00-16:00', '16:00-20:00', '20:00-24:00')), '访客预约时间段标签'),
  -- 环境自适应与安全基线（对齐 Alembic 0003）
  ('adaptive.enabled',                JSON_OBJECT('value', true),        '环境自适应模块开关'),
  ('adaptive.mode',                   JSON_OBJECT('value', 'rule_only'), 'off / rule_only / vlm / vlm_weather'),
  ('adaptive.vlm_provider',           JSON_OBJECT('value', 'deepseek'),  '当前 VLM provider'),
  ('adaptive.vlm_interval_seconds',   JSON_OBJECT('value', 60),          'VLM 调用最小间隔'),
  ('adaptive.weather_enabled',        JSON_OBJECT('value', false),       'Open-Meteo 天气佐证开关'),
  ('adaptive.current_profile',        JSON_OBJECT('value', 'normal'),    '当前生效 profile'),
  ('adaptive.last_reason',            JSON_OBJECT('value', 'default profile'), '最近策略原因'),
  ('adaptive.expires_at',             JSON_OBJECT('value', ''),          '当前策略过期时间'),
  ('rec.det_thresh.base',             JSON_OBJECT('value', 0.50),        '检测阈值安全基线'),
  ('rec.spoof_thresh.base',           JSON_OBJECT('value', 0.85),        '活体阈值安全基线'),
  ('rec.match_thresh.base',           JSON_OBJECT('value', 0.40),        '匹配阈值安全基线'),
  ('rec.quality_thresh.base',         JSON_OBJECT('value', 0.50),        '质量阈值安全基线'),
  ('rec.consensus_frames.base',       JSON_OBJECT('value', 3),           '多帧共识安全基线'),
  -- UI 主题（来源 swu-context.md §六，前端 P7 直接读取）
  ('ui.theme.primary',         JSON_OBJECT('value', '#003D7A'), '主题主色（西大蓝）'),
  ('ui.theme.secondary',       JSON_OBJECT('value', '#B22222'), '主题辅色（西大红）'),
  ('ui.theme.gold',            JSON_OBJECT('value', '#D4AF37'), '主题装饰色（校徽金）')
ON DUPLICATE KEY UPDATE `config_key`=`config_key`;

-- 人员、人脸、通行记录和访客数据均由部署者自行创建，不提供演示隐私数据。
