-- Registra todas as migrations como já aplicadas no django_migrations.
-- Use ON CONFLICT DO NOTHING para não duplicar as que já rodaram parcialmente.
-- Execute no Supabase SQL Editor ANTES do próximo deploy.

INSERT INTO django_migrations (app, name, applied) VALUES
  -- contenttypes (dependência base de tudo)
  ('contenttypes', '0001_initial',                              NOW()),
  ('contenttypes', '0002_remove_content_type_name',             NOW()),

  -- auth
  ('auth', '0001_initial',                                      NOW()),
  ('auth', '0002_alter_permission_name_max_length',             NOW()),
  ('auth', '0003_alter_user_email_max_length',                  NOW()),
  ('auth', '0004_alter_user_username_opts',                     NOW()),
  ('auth', '0005_alter_user_last_login_null',                   NOW()),
  ('auth', '0006_require_contenttypes_0002',                    NOW()),
  ('auth', '0007_alter_validators_add_error_messages',          NOW()),
  ('auth', '0008_alter_user_username_max_length',               NOW()),
  ('auth', '0009_alter_user_last_name_max_length',              NOW()),
  ('auth', '0010_alter_group_name_max_length',                  NOW()),
  ('auth', '0011_update_proxy_permissions',                     NOW()),
  ('auth', '0012_alter_user_first_name_max_length',             NOW()),

  -- admin
  ('admin', '0001_initial',                                     NOW()),
  ('admin', '0002_logentry_remove_auto_add',                    NOW()),
  ('admin', '0003_logentry_add_action_flag_choices',            NOW()),

  -- sessions
  ('sessions', '0001_initial',                                  NOW()),

  -- accounts
  ('accounts', '0001_initial',                                  NOW()),
  ('accounts', '0002_initial',                                  NOW()),

  -- core
  ('core', '0001_initial',                                      NOW()),

  -- courses
  ('courses', '0001_initial',                                   NOW()),
  ('courses', '0002_initial',                                   NOW()),

  -- professors
  ('professors', '0001_initial',                                NOW()),

  -- allocations
  ('allocations', '0001_initial',                               NOW()),
  ('allocations', '0002_initial',                               NOW()),

  -- extra_curricular
  ('extra_curricular', '0001_initial',                          NOW())

ON CONFLICT (app, name) DO NOTHING;
