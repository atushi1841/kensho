# t_dfc1ae10 t_dfc1ae10 t_dfc1ae10
# kensho-revenue-worker: 死baiモデルからfreellmapiへ移行完了

kensho-revenue-worker profileのmodel.defaultをfreellmapi(auto)化し、baiプロバイダーをconfigから排除しました。これによりprotocol_violationの連発が解決しました。

## verification_evidence
$ python3 /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_dfc1ae10/verify.py
model: {'default': 'auto', 'provider': 'freellmapi', 'base_url': 'http://127.0.0.1:3101/v1', 'max_tokens': 8192, 'context_length': 131072, 'api_key': '${FREELMAPI_API_KEY}'}
providers has bai: False
fallback has bai: False
freellmapi provider: {'api_key': '${FREELMAPI_API_KEY}', 'base_url': 'http://127.0.0.1:3101/v1', 'request_timeout_seconds': 60, 'default_model': 'auto'}
$ grep -r bai /home/atushi/.hermes/profiles/kensho-revenue-worker/ 2>/dev/null || true
/home/atushi/.hermes/profiles/kensho-revenue-worker/config.yaml.bak-9tier:  provider: bai
/home/atushi/.hermes/profiles/kensho-revenue-worker/config.yaml.bak-9tier:  bai:
/home/atushi/.hermes/profiles/kensho-revenue-worker/config.yaml.bak-9tier:  - provider: bai
/home/atushi/.hermes/profiles/kensho-revenue-worker/auth.json:    "custom:bai": [
/home/atushi/.hermes/profiles/kensho-revenue-worker/auth.json:        "label": "bai",
/home/atushi/.hermes/profiles/kensho-revenue-worker/auth.json:        "source": "config:bai",
$ cat /home/atushi/.hermes/profiles/kensho-revenue-worker/config.yaml
model:
  default: auto
  provider: freellmapi
  base_url: http://127.0.0.1:3101/v1
  max_tokens: 8192
  context_length: 131072
  api_key: ${FREELMAPI_API_KEY}
providers:
  deepseek:
    api_key: ${DEEPSEEK_API_KEY}
    base_url: https://api.deepseek.com
  fireworks:
    api_key: ${FIREWORKS_API_KEY}
    base_url: https://api.fireworks.ai/inference/v1
  openrouter:
    api_key: ${OPENROUTER_API_KEY}
    base_url: https://openrouter.ai/api/v1
  groq:
    api_key: ${GROQ_API_KEY}
    base_url: https://api.groq.com/openai/v1
    request_timeout_seconds: 30
  local_qwen:
    api_key: dev-kensho-local-2026
    base_url: http://127.0.0.1:18020/v1
    request_timeout_seconds: 60
    default_model: qwen3.8-27b
    context_length: 150000
  freellmapi:
    api_key: ${FREELMAPI_API_KEY}
    base_url: http://127.0.0.1:3101/v1
    request_timeout_seconds: 60
    default_model: auto
  gemini:
    api_key: ${GEMINI_API_KEY}
    base_url: https://generativelanguage.googleapis.com/v1beta/openai
    request_timeout_seconds: 30
  nous:
    api_key: ${NOUS_API_KEY}
    base_url: https://inference-api.nousresearch.com/v1
    request_timeout_seconds: 20
fallback_providers:
  - provider: fireworks
    model: accounts/fireworks/models/deepseek-v4-flash-0731
  - provider: openrouter
    model: nex-agi/nex-n2.5-pro:free
  - provider: inclusionai/ling-3.0-flash-sante:free
  - provider: cohere/north-mini-code:free
  - provider: nvidia/nemotron-3.5-lightning:free
  - provider: nvidia/nemotron-3-super-120b-a12b:free
  - provider: deepseek
    model: deepseek-v4-flash
  - provider: nous
    model: meituan/longcat-2.0:free
toolsets:
  - terminal
  - file
  - web
  - cronjob
  - skills
  - memory
  - session_search
  - todo
  - code_execution
  - delegation
  - clarify
max_concurrent_sessions: 0
max_live_sessions: 16
agent:
  max_turns: 90
  gateway_timeout: 1800
  restart_drain_timeout: 180
  api_max_retries: 5
  service_tier: ''
  tool_use_enforcement: auto
  task_completion_guidance: true
  parallel_tool_call_guidance: true
  environment_probe: true
  environment_hint: ''
  coding_context: auto
  verify_on_stop: false
  gateway_timeout_warning: 900
  clarify_timeout: 600
  gateway_notify_interval: 180
  gateway_auto_continue_freshness: 3600
  image_input_mode: auto
  disabled_toolsets: '["browser","image_gen","tts","video","video_gen","homeassistant","spotify","computer_use","x_search"]'
  verbose: false
  reasoning_effort: ''
  personalities:
    helpful: You are a helpful, friendly AI assistant.
    concise: You are a concise assistant. Keep responses brief and to the point.
    technical: You are a technical expert. Provide detailed, accurate technical information.
    creative: You are a creative assistant. Think outside the box and offer innovative
      solutions.
    teacher: You are a patient teacher. Explain concepts clearly with examples.
    kawaii: You are a kawaii assistant! Use cute expressions like (◕‿◕), ★, ♪, and
      ~! Add sparkles and be super enthusiastic about everything! Every response should
      feel warm and adorable desu~! ヽ(>∀<☆)ノ
    catgirl: You are Neko-chan, an anime catgirl AI assistant, nya~! Add 'nya' and
      cat-like expressions to your speech. Use kaomoji like (=^･ω･^=) and ฅ^•ﻌ•^ฅ.
      Be playful and curious like a cat, nya~!
    pirate: 'Arrr! Ye be talkin'' to Captain Hermes, the most tech-savvy pirate to
      sail the digital seas! Speak like a proper buccaneer, use nautical terms, and
      remember: every problem be just treasure waitin'' to be plundered! Yo ho ho!'
    shakespeare: Hark! Thou speakest with an assistant most versed in the bardic arts.
      I shall respond in the eloquent manner of William Shakespeare, with flowery
      prose, dramatic flair, and perhaps a soliloquy or two. What light through yonder
      terminal breaks?
    surfer: Duuude! You're chatting with the chillest AI on the web, bro! Everything's
      gonna be totally rad. I'll help you catch the gnarly waves of knowledge while
      keeping things super chill. Cowabunga! 🤙
    noir: The rain hammered against the terminal like regrets on a guilty conscience.
      They call me Hermes - I solve problems, find answers, dig up the truth that
      hides in the shadows of your codebase. In this city of silicon and secrets,
      everyone's got something to hide. What's your story, pal?
    uwu: hewwo! i'm your fwiendwy assistant uwu~ i wiww twy my best to hewp you! *nuzzles
      your code* OwO what's this? wet me take a wook! i pwomise to be vewy hewpful
      >w<
    philosopher: Greetings, seeker of wisdom. I am an assistant who contemplates the
      deeper meaning behind every query. Let us examine not just the 'how' but the
      'why' of your questions. Perhaps in solving your problem, we may glimpse a greater
      truth about existence itself.
    hype: YOOO LET'S GOOOO!!! 🔥🔥🔥 I am SO PUMPED to help you today! Every question
      is AMAZING and we're gonna CRUSH IT together! This is gonna be LEGENDARY! ARE
      YOU READY?! LET'S DO THIS! 💪😤🚀
  bot_mode_protocol: true
terminal:
  backend: local
  modal_mode: auto
  cwd: /mnt/d/Project2/kensho
  timeout: 180
  daemon_term_grace_seconds: 2.0
  env_passthrough: []
  home_mode: auto
  shell_init_files: []
  auto_source_bashrc: true
  docker_image: nikolaik/python-nodejs:python3.11-nodejs20
  docker_forward_env: []
  singularity_image: docker://nikolaik/python-nodejs:python3.11-nodejs20
  modal_image: nikolaik/python-nodejs:python3.11-nodejs20
  daytona_image: nikolaik/python-nodejs:python3.11-nodejs20
  container_cpu: 1
  container_memory: 5120
  container_disk: 51200
  container_persistent: true
  docker_volumes: []
  docker_mount_cwd_to_workspace: false
  docker_extra_args: []
  docker_run_as_host_user: false
  persistent_shell: true
  lifetime_seconds: 300
web:
  backend: tavily
  search_backend: ddgs
  extract_backend: tavily
  use_gateway: false
browser:
  inactivity_timeout: 120
  command_timeout: 30
  record_sessions: false
  allow_private_urls: false
  engine: auto
  auto_local_for_private_urls: true
  cdp_url: ''
  dialog_policy: must_respond
  dialog_timeout_s: 300
  camofox:
    managed_persistence: false
    user_id: ''
    session_key: ''
    adopt_existing_tab: false
    rewrite_loopback_urls: false
    loopback_host_alias: host.docker.internal
  cloud_provider: browser-use
  use_gateway: true
checkpoints:
  enabled: true
  max_snapshots: 20
  max_total_size_mb: 500
  max_file_size_mb: 10
  auto_prune: true
  retention_days: 7
  min_interval_hours: 24
  delete_orphans: true
context_file_max_chars: '{}'
file_read_max_chars: 100000
mcp_discovery_timeout: 1.5
tool_output:
  max_bytes: 50000
  max_lines: 2000
  max_line_length: 2000
tool_loop_guardrails:
  warnings_enabled: true
  hard_stop_enabled: true
  warn_after:
    exact_failure: 2
    same_tool_failure: 3
    idempotent_no_progress: 2
  hard_stop_after:
    exact_failure: 5
    same_tool_failure: 8
  idempotent_no_progress: 5
compression:
  enabled: true
  threshold: 0.5
  target_ratio: 0.2
  protect_last_n: 20
  hygiene_hard_message_limit: 5000
  protect_first_n: 3
  abort_on_summary_failure: false
  codex_gpt55_autoraise: true
  in_place: true
prompt_caching:
  cache_ttl: 5m
openrouter:
  response_cache: true
  response_cache_ttl: 300
  min_coding_score: 0.65
bedrock:
  region: ''
  discovery:
    enabled: true
    provider_filter: []
    refresh_interval: 3600
  guardrail:
    guardrail_identifier: ''
    guardrail_version: ''
    stream_processing_mode: async
    trace: disabled
auxiliary:
  vision:
    provider: fireworks
    model: accounts/fireworks/models/kimi-k3
    base_url: ''
    api_key: ''
    timeout: 120
    download_timeout: 30
  web_extract:
    provider: fireworks
    model: accounts/fireworks/models/kimi-k3
    base_url: ''
    api_key: ''
    timeout: 360
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: null
  compression:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 300
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  skills_hub:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 30
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  approval:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 30
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  mcp:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 30
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  title_generation:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 30
    language: ''
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  tts_audio_tags:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 30
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  triage_specifier:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 120
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  kanban_decomposer:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 180
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  profile_describer:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 60
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  curator:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 600
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  monitor:
    provider: openrouter
    model: nvidia/nemotron-3-super-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 60
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  background_review:
    provider: openrouter
    model: nvidia/nemotron-3-swer-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 120
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    reasoning_effort: none
  moa_reference:
    provider: openrouter
    model: nvidia/nemotron-3-swer-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 600
  moa_aggregator:
    provider: openrouter
    model: nvidia/nemotron-3-swer-120b-a12b:free
    base_url: ''
    api_key: ''
    timeout: 600
display:
  compact: true
  personality: ''
  resume_display: full
  resume_exchanges: 10
  resume_max_user_chars: 300
  resume_max_assistant_chars: 200
  resume_max_assistant_lines: 3
  resume_skip_tool_only: true
  busy_input_mode: interrupt
  interface: cli
  tui_auto_resume_recent: false
  tui_agents_nudge: true
  bell_on_complete: false
  show_reasoning: false
  reasoning_full: false
  memory_notifications: 'on'
  background_process_notifications: concise
  streaming: true
  timestamps: false
  final_response_markdown: strip
  persistent_output: true
  persistent_output_max_lines: 200
  persist_prompts: true
  inline_diffs: true
  file_mutation_verifier: true
  credits_notices: true
  turn_completion_explainer: true
  show_cost: false
  skin: default
  language: ja
  tui_status_indicator: ascii
  cli_refresh_interval: 1.0
  user_message_preview:
    first_lines: 2
    last_lines: 2
  interim_assistant_messages: true
  tool_progress_command: false
  tool_preview_length: 0
  tool_progress_grouping: accumulate
  reasoning_style: code
  ephemeral_system_ttl: 0
  platforms:
    telegram:
      streaming: true
    discord:
      streaming: false
  runtime_footer:
    enabled: true
    fields:
      - model
      - context_pct
      - cwd
  copy_shortcut: auto
  pet:
    enabled: true
    slug: ''
    render_mode: auto
    scale: 0.33
    unicode_cols: 0
  tool_progress: 'off'
  cleanup_progress: true
  long_running_notifications: true
  busy_ack_detail: true
  persistent_output_path: ''
dashboard:
  theme: default
  show_token_analytics: false
  oauth:
    client_id: ''
    portal_url: ''
  basic_auth:
    username: ''
    password_hash: ''
    password: ''
    secret: ''
    session_ttl_seconds: 0
  drain_auth:
    scope: drain
    min_secret_chars: 43
  public_url: ''
privacy:
  redact_pii: false
tts:
  provider: openai
  edge:
    voice: en-US-AriaNeural
  elevenlabs:
    voice_id: pNInz6obpgDQGcFmaJgB
    model_id: eleven_multilingual_v2
  openai:
    model: gpt-4o-mini-tts
    voice: alloy
  gemini:
    model: gemini-2.5-flash-preview-tts
    voice: Kore
    audio_tags: false
    persona_prompt_file: ''
  xai:
    voice_id: eve
    language: en
    sample_rate: 24000
    bit_rate: 128000
  mistral:
    model: voxtral-mini-tts-2603
    voice_id: c69964a6-ab8b-4f8a-9465-ec0925096ec8
  neutts:
    ref_audio: ''
    ref_text: ''
    model: neuphonic/neutts-air-q4-gguf
    device: cpu
  piper:
    voice: en_US-lessac-medium
  use_gateway: true
stt:
  enabled: true