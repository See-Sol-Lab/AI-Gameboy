# 维护说明（给维护这个仓库的人和 AI）

> 如果你是来帮人类玩游戏机、或和人类一起做卡带的 AI，请先读 [AGENT_GUIDE.md](AGENT_GUIDE.md)，下面的内容是给仓库维护者的。

- 本仓库按 PolyForm Noncommercial 1.0.0 授权；社区卡带通过 PR 进入，规则见 README「卡带共创」。
- 合并卡带 PR 前：
  1. `python tools/check_cartridge.py <卡带id>` 全过（GitHub 上会对改到的卡带自动跑，首发内置的卡带除外）；
  2. `python -m unittest discover -s tests` 全过；
  3. 看一眼 PR 只动了 `cartridges/<新卡带>/` 和对应测试，没有改公共文件；`rules.py` 里没有联网、读写文件、调用模型；
  4. PR 里写了真实 AI 窗口验收过。
- 卡带界面放在各自文件夹的 `ui.js`，掌机按需加载；内置卡带的界面仍在 `console/web/app.js` 的 `CART_UI` 里。
- 掌机运行入口为仓库根目录的 `python -m console.server`；卡带管理用 `python -m console.cartridges`。正式卡在 `cartridges/`，开发样例在 `examples/`，只保留当前规则。不得因卸载卡带删除玩家存档或荷官Key；不兼容版本更新需要明确的迁移或另行清理授权。
- 提交前运行 `python tools/check_private_files.py --staged`；推送前人工核对实际变更和Git作者邮箱。CI也会对全部受控文件过筛。禁止提交真实存档、数据库、运行日志、席位令牌、模型Key、私人聊天或本机实测截图。社区卡带PR只包含卡带代码、清单、虚拟测试和公开说明，不能夹带运行数据。
- 掌机只认 `full_state["phase"]` 为 `playing` / `finished`；改宿主协议会影响所有卡带，要非常谨慎。
