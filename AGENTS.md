# 维护说明（给维护这个仓库的人和 AI）

- 本仓库按 PolyForm Noncommercial 1.0.0 授权；社区卡带通过 PR 进入，规则见 README「卡带共创」。
- 合并卡带 PR 前：
  1. `python tools/check_cartridge.py <卡带id>` 全过（GitHub 上会对改到的卡带自动跑，首发内置的卡带除外）；
  2. `python -m unittest discover -s tests` 全过；
  3. 看一眼 PR 只动了 `cartridges/<新卡带>/` 和对应测试，没有改公共文件；`rules.py` 里没有联网、读写文件、调用模型；
  4. PR 里写了真实 AI 窗口验收过。
- 卡带界面放在各自文件夹的 `ui.js`，掌机按需加载；内置卡带的界面仍在 `web/app.js` 的 `CART_UI` 里。
- 掌机只认 `full_state["phase"]` 为 `playing` / `finished`；改宿主协议会影响所有卡带，要非常谨慎。
