# Odyssey Void

Backup portátil (dotfiles) da configuração do desktop Odyssey, sem credenciais nem dados pessoais.

## O que contém

- Shell: `.bashrc`, `.bash_profile`, `.inputrc`
- Desktop: mango, waybar, swaync, rofi, fuzzel, kitty, cava, fastfetch, mako, qt6ct, GTK, XFCE/Thunar, Zed, mpv-related scripts
- `~/.config/scripts` (scripts e paletas de cores)
- `~/.config/opencode/opencode.jsonc` (sem token, sem `node_modules`)
- `packages/manual.txt` (pacotes XBPS marcados como manuais, sem versões — apenas referência)

## O que NÃO contém

- Firefox/Perfil, histórico, cookies, senhas salvas, sessões e telemetria
- Qualquer configuração do GitHub CLI (`gh/`), chaves SSH, cookies do PulseAudio, dconf
- Estados de primeira execução, caches, bytecodes e assets binários pessoais
- Caminhos absolutos do usuário original: são gravados como `__HOME__` e expandidos no install

> A única menção a e-mail nos arquivos é o cabeçalho SPDX de autoria de terceiros nos shaders do cava; não é dado do usuário deste backup.

## Instalar em outra máquina

```bash
git clone https://github.com/<seu-usuario>/odyssey-void.git
cd odyssey-void
./install.sh
```

Opções:

```bash
./install.sh --dry-run          # mostra o que seria feito
./install.sh --skip-existing    # não sobrescreve arquivos já existentes
./install.sh --target /caminho  # instala em outro HOME (útil para testar)
./install.sh --no-backup        # não cria backup dos arquivos substituídos
```

Por padrão, antes de sobrescrever qualquer arquivo, o instalador salva a versão anterior em `~/.odyssey-void-backup/<timestamp>/`. Arquivos executáveis mantêm a permissão original.

Dependências dos apps (mango, waybar, kitty, rofi, fuzzel, swaync, cava etc.) não são instaladas automaticamente — o script apenas copia as configurações. `packages/manual.txt` é uma referência para reconstruir o ambiente; inclui itens específicos desta máquina (bootloader, firmware, drivers de GPU) e deve ser revisado antes de usar em outro hardware.

## Atualizar o backup

Na máquina original:

```bash
./scripts/update-backup.sh
./scripts/check-secrets.sh
```

O script de atualização usa `manifest.txt`, substitui o HOME actual por `__HOME__` e nunca copia arquivos fora da lista. Ele também regenera `packages/manual.txt` com `xbps-query -m` (sem versões); sem `xbps-query`, o arquivo existente é preservado.

## Segurança

`scripts/check-secrets.sh` procura padrões de token/chave antes de cada push. `gh/hosts.yml`, `mozilla/`, `pulse/cookie`, `dconf/user`, `qBittorrent/` e arquivos de estado estão fora do manifest e também protegidos por `.gitignore`.
