"""口袋夜铺 · 单文件盲玩版 0.3.0

给 AI 玩家：你需要有 Python 代码执行能力；Python 3.11+，无需第三方依赖。
下载这个文件后即可玩，不需要整个仓库、MCP、网络或模型 API Key。

    import pocket_night_shop as shop
    print(shop.cmd("help"))
    print(shop.cmd("observe"))
    # 新局先请你的人类替你掷启动资金(11-66),不得自己掷,再登记:
    print(shop.cmd('set_start_funds {"amount":人类掷出的数}'))
    print(shop.cmd('run_shifts {"focus":"scavenge","count":6,"stop_on":"new"}'))

只根据 observe 返回的 legal_actions 和结果自己决定；无需每轮发表感想。
不要解码下面的 _RULES_B64，也不要打开原仓库规则或读取存档里的隐藏字段，
那会提前揭露旧物、秘密与客人需求。通过淘货、修复和相遇慢慢发现。
这只是防误读的盲玩包装，不是加密或防作弊安全措施。

每次行动自动保存到本文件旁的 pocket_night_shop.save.sqlite3。
下次导入同一文件并调用 observe 即可继续。无需保持 Python 进程一直运行。
保存目录需可写；只复制 .py 不会带走已有存档，迁移时也要备份 .sqlite3。
独立版与掌机各有自己的存档，本版没有掌机网页。

命令行也能用：python pocket_night_shop.py observe
本文件由 tools/build_night_shop.py 生成，请维护原规则和模板后重新生成。
Copyright See-Sol-Lab and the AI-Gameboy contributors.
License: PolyForm Noncommercial 1.0.0，完整协议附在文件末尾。
"""
import base64 as _base64
from contextlib import closing as _closing
import json as _json
from pathlib import Path as _Path
import secrets as _secrets
import sqlite3 as _sqlite3
import sys as _sys
import zlib as _zlib

VERSION = "0.3.0"
SAVE_PATH = _Path(__file__).resolve().with_name("pocket_night_shop.save.sqlite3")
_RULES_B64 = (
    "eNq1vWlTXFeWLvxdv4LLjTcKqrJclmS73KrSG+Gu645S3KpyR5dvR79BEASClESbqRks+yoUAULMs5gFSAKBQBODhJiS4b/c"
    "4pzM/NR/4T7PWvvss8/JkwiX+3U47CTznD2uvcZnrV1aWvq3jgFv9HluedBbWchPHP6tY/D7Tz+5+p9Hj397Jbs27M+sZftf"
    "/q2j88svzo6H/YX+/NyYv7jqbSyf7Y+cHU7mZ3fzU6fZw9NsZjQ3tvq3jgeXLn11o8Sf3fQmN8/2O7IjL72N3f88mvf7O/j2"
    "41F/4TCbmfCfLGQnt9GB93bM63nvbTzGq972VHblMPt60xt95Y+s+pO7Xvcb76gjt/bA23zqPRrKLx16h6P+zKp3OsOu/P6D"
    "fO9obmnIG1j3Ftb96S1vdDw7soXxnh0OnmV28SH34aF/OJY7OchODXkrD88OV3Kns+gy+3baX+z6z6Ohs/1hf/5UB+oPrJ5l"
    "9vy+aa/30JvcyM2MehOd7Km0tPTSpbqG5qaWtpI71a136utuXrrV0tRQUtPU/GOJ+aE2nW7m35cu/fWPN/7p27+WXC+pKM1n"
    "Hvqzo6WpklJ/bxtrXFp56Z+++cMN+a01XV/PX1rSzdV1LfzUWlP9fbrxdpqfa9pbqtvkU3vz7ZbqWvnYVlf7o75S82NNvXxV"
    "W9faUNfaiob//M03/0N79Reeeifd/PVsf8J/v85P2YGD3PZr+dT1InfYKZ8W9vzOQfk0/c7vkl+9kxn/4Sib++rfqv76x2/+"
    "uepPX//r139Cu5/LV3/4X3/99ps/f/0vVf964683ZJZfyvf/+NW3f/gj/vri0qUb3379ZxnIpRL8U1Z6t7qt5o603bmAjfLm"
    "57MPDrKPH/odHbklGRz+l52f9nq6z07WvL5MdrED1OONrvrvlryeOW9jCE/nOyf8t/3YDrxwJVXyRUpax9DXHuUf9eV7h0EA"
    "uQ9bIAZ/Zjflb456Ky9BSmdHj22f2Gn/6djZ/quzw0Nv5TGGw276evKPnrLd8pQZ8HdpWeXcxkp+ci4/s87eMw/zEwv5R6ve"
    "0JxMZaPL78ig5fzis9zpeH5uKDv5FI/mJzvRvXeywX9Bjl1v7Yg/D0aMd7MLT/23z9EBlhutkwpnN/F6KtcxhE/+/AmP1PJr"
    "DBQP4ens2tbZ8QKIFE97C1v+9EFkxKCcllscV35+XeY97j+e5hLPrHnzO97eiWzy4am3suOd9GHuKW94B0chOzWHxfb3lvAv"
    "Hs8+fpB/MWdH/Fkw4tzSqrd67C90eGMjWDKsoGlrbCSl7WOZcxsYIk54B9YDD/lvlvzBVX9gm8PYf+kdvoiM+GZdS60M6uiQ"
    "nKK/N3vanevp4MMLh/7yVn7/qRLwQHZnjfNZXJLeNrrQlb+w6A3N4Fh7o6+5hc+3dMyXUyVfBmMGOWiTuefdGDxfti17k9s4"
    "41zK7l1v4wlWXGb1DmtDnvf4Ye50Mtf3ylsc85/1RoZdn25rS8thJWH2bbH34QG+cfIk1zl0drokhz1YKXInsLOFfl017Kg3"
    "OuytDPu7D/yRfg5gDExwxq74VUvVh/ve0bOz0w08zKHjzdg7/oeNs8Meb/4JODJ3U2kIo8IYQDZCVWDu+5Hht6Wra9qbdYj9"
    "2UxP7vmD7CHPYm5iMTe06y9uym+Lm97hVHYyOIiHa2jcezsLcuejxy+yr5OIRNoCqeSPx2S1pRV9mifo0VPu3OwJuPzZ/iA3"
    "ffQtzlfutJdz6pvBk5Gx1lQ3pFuqZamxhIPDWO1c15B3TILKzu9jM+W3/pdnx3O5rl2QkD+15a0NZjN9QS/4t8tSxj8EA81P"
    "LYB27dqyaSGG7Js3eB7Lrt2kSNPHbzA+PJ1dGPTGxvGoP/4w19EdJWXDyMGtsKogxvzT95zS1mh+okt+GO81bCk/B9IaZ1+d"
    "W97WrPSQwb/ZF+AlW4XMDQ3k+oY4zpGnpKjMsNtJ6uy4x4jWzhlvZRvCmuxubAhd8YhsdHmdo0J5g1FucadJZAfYJWd30pc7"
    "XcjtbXLMw1NY7OzjjfwTkQv4H/bQWzkwlIC1WXmV63/HXV1dt0trWZs+r+wiPK5kkzPrOK653ldYCCwq1tIbfSFM/hXewSSU"
    "tsDX8FN0sOl07c2mH4RXgMVO9nH1RHXIT3Rm5x/JD/OPRH6QmV0DreZedFIjmNsBL/T7J6BF2KX9rR3qZB+YNangiIc1hTby"
    "veFpzb57ZEYOjvoc5/wtmFBu4Ji9j2Syj7p0DFHmUN2gZ6tjKp/hLueWp7Ojw9lOOVXZHuz6JroCCwCb595jOfa2zw43ch/2"
    "CsUEWCw2BaqQrqXfP6z6DRc1272G17hgEBZ9p/mZHYwdXOfsoBsEwuO/vKUH62x/Ibd6GhlmQ3trXY1ZUm+LvDo38MCfGfRO"
    "BoUlvib96sJCjOY7lv2pHUjPVPblIbg1j/KD53gDEzjLjIB0qFgdPQMbKmTC2S1okL0hT9CnuYZHhzhMZwdPDbXuQihtp7wu"
    "kOsKKXD+ERYXJ/nscMQb6/NWRyMzuF3f9H1aj9wJtjw/sZt916/izu8f9FZn5LehXm9rOvt83R+GOjSDtlWsKgfOrb3AGvmz"
    "T735k4S1P1qkwJMWOG7tQQnCXxrKLy7nxo79vjFSMJZclI3s0YTfveyNznpDInpt03bYjU1t6ZtNTd/JyVr6kH3W6XU84vih"
    "RINYdl74C2/kXO4OeCckyuxpJgWFl/qc0Ax+8GdeFrKJs4MXuYcDlk3ITs0d519MoxfytpEtiorDmbP9jD87Iodi2Ejs/UEh"
    "ko7sm0l/chMPR1lbe1tbU+O/V4vEgyD1M0uq6mQPj/3+5+FhOB4z5ELJ/+RxvuuYe5kZoeAYG/IOds4yfDq39NxfGIZg8gd7"
    "DFeKChE0BIOEp9IwkO5dHD1tVPs0mzADmZQhoUNPOu0Fe/FWpkFI4KX+1DsdVFTy1TXevVOtOjObGD3wtyZJy2AiYHfv9mWG"
    "3QfoDYq/YXdbo/6jDf/DXnZ+zNK2ZSBGKdkY8rrXaZsoG7HtiTQRLUg5tnRo9DvVP0wPGx/84w2jwmC4lapAV/3PG38Rdf6e"
    "dGeU6GtY45ldHHeOlmoqvvCOH+FMGfsBWiC+ys9B75VnRM3iW6L6lOrYAy3mGnXcLe+0R2wLVQ2kh1VvX9bDiODIcyLt2O1m"
    "BvImaFFECp+DJFkaksEYvn1N+fbUKb8UDslvutdAiPzGMiMO++n7s4OxoEk95ByPnCQ+bA8Qe9p5kZ3fkBFZIpXBr4HI1Fgy"
    "O+5O//6lS4EF45ooNU3tLXWq1+U+QHa+hm5CGUdet+HtSTd+13u//4TiNLOb6zrmGkM7pwg1wjMwlx+U2nOZmfYHBlRw+gOz"
    "KmyhfYMqjCK1uu5PrpI7nfRBz1Uiq3BWMdxts82VIMJPI/rcHR13vqPj7IhCB2am/2wp19Hp7feZcZ8dbJlxn85i6ND6oamr"
    "DgFzV/c2Iissja8e5Gc2YBV7kD7dfVCwwEjO9qFvDOfnd/OPtkUFUQJ/PXSWyZwdT2kruZ0PdjaWdswGYw5fhtIoXXOnurGu"
    "RtZ+eRqnH0zdf0elFGwgO9bj7a2aaUAJw7+50zmwMpF3/dq1WlPe6Irf8coaELF9ACPK9m17m4/8xw9T/vMO/ylk0mnueIPm"
    "2vBOfvEJaD7XMeaddgXjDojG0jrX/qod+N262qa7Ku4z3j6UmRXu9dET7iwW/0UvyCNON3n4Ocb6wJ5VaAvR8LAVkg5WnroR"
    "Fl+W03JESt19Mm9v5ZU3Ztc4PLPh2TeHDKP+h1CbamuvTTe2CRcECUC9me30V49INm9f4JxKCzDhXnSCTrz9DVVRsIM4bvCn"
    "aJOgmWxmLZt5qwc7mXLEraS75K1Oo/V87zhMk5RRKYdhNb4D84Z8zr48taRiD3XIIQz3wDR+G9J9dV19k5C937fjLfRkF46g"
    "1XPln3dCdhvXB6XCZkYWf0T5AtxIVBD2VjmqbqOlFw6e53Z8n8d1v8ufnqP/6GhWxBHE8kmH//AUPhKYF0p4xs7eW831061w"
    "lpmlPH1wEO5NwJLM3pCOLodbYucCJqAKXG6tk1IH7W7tYLwFp7jrOLfZieUBn4DGDKsg+3DX2meJbCh3+JqmNOY7uuLtd1Is"
    "qxMAlKvCDgLWG908y8Bk/4ADL6JxF/I2gSfZc2E4c4TC4JdqEQ0H0t+HuF/qy7/o8eceg39xfzqHvPFZ91iMKIujsw584niK"
    "/jcxZewWJbKlLM4vPEIyV4zL7+omK5LTcej19mSXNmAaZ99O4gTll2c5cVV/Jk+8jeP88sPsxky4PwGPDcnPOfFXVCh/9ed/"
    "vPH1X761QoOuFmwPJD89KIPz2f4hP7OjOiH0AhjXUODhcuiHcKC/CTrLy+3sqxlyUjieoI/JbofTgpdlhgbC4qjw2I7s/Gjq"
    "LDOApcudzqsXip7Xw0MoV/7mpHfwnoxjfsd/15/PzDrt5B9Pes87oaN6Q93kMx2d0M1V2aCnd3gaNjM1t6U3+kzKsNPHD8Ru"
    "7Ef38AJ54++dNmkknPRYwYi99fb2cMZV/UqpwpXbe4q1UIs2v9Cr08jPfnDakeYPyShBYm9PoOCqWY+RgLXjDfw3ZdwnGZgz"
    "WKKnOBDYRacRb3vQfzWm9Jwdeu0PL0tXr+Ckzh5v0IrgSZgfzy4+h7DA3mKCVliQja4ew119tv/YXbTnIxgVOcbYAVQ5s4lH"
    "iyn/6YI3umU6g1dme9wfecRtxg6u9qrEUU+Pu5UdnfB3wByQga2ojzEFOwqNYpt57jBIsTU5Qtqd46qlayOgt0v/8tW/3Pj2"
    "xteiA0JBaWhoaoQqU0bSVFb/2ZegznJ6iBvdn7fGwT6oVn8mP+uRMf+UtlS3pPWx1V6YplRpPzWtVDfW1FE08FdxHa2wD/ik"
    "+OOddF1LfVNTg/wKb8PZ/rTxWJXfV31Vhvv/JSisZmyhwhp+YRXW8KtQDQ2+Myqr0RzDJyNqX/h1qNvaZUmF+mn4nTYbariy"
    "MjGF1G3B1T2dQRhtON5uoHe7LbgKadCboyWHD1rN12n1/qU/ffOHr7698c1fHKOgvrqRz90rbcQ0Au0X7tK9PQkNpFtrWuqa"
    "2+qEMkpdTQNsFx5Feo1OZ40QPDTWGMbRSiK4HKUcDqa+qea7KvPzpxp7qMFIoTm3yjexF5qbmrg2FWEAwDjWrbc6dEcGrpOI"
    "wRk6W2X7Ku8HxkZbtZlUOHPv8Kl31KXexsTJGyGjWi/0AMhxeHl5qGemcqcH0clfic2lcP5fFsz/s4R3Cpcg8L2F3k3XHeN6"
    "CIS07Jxr0XdkwvQewIuZmfAOJxImTHHd94qavlj4KrOx7d7Rg0A7sLO9ev5WX75SMNcvi+51fIsDP79rfzsuPSV1zvL+JcSZ"
    "/vKtS93p6luRKUPiwjwXPgw/y65S0A9t8tNzyIsRSsmjRSvw4HqCbgQNR0W1fZGzD9a1JX2rvbE20k3u9CnepwIkJo7bDfU8"
    "kcF+/ywlMehp/gl9aJlZEQMrokVRw7IrXNfIBbty3+FjVc26sE6XIvoRxIJXz+0Par+qDxrfglKJB4zkpRN5M2WUitE+nGd9"
    "lCbSWtA/govt9rRcDgbRXN1Sk66PcY5njCsMdeeeH0QWFnrZzprI7G1dVSigFNX79Jp7x8vZgV2rdKZgN+gi+GNwnI/ldg4c"
    "tc0hl5o7TXU1Qkn3SqtratLNuhz11TdlWNAdZ6/YpUQoGEScUkeumm7uUb1feO7crmrTNfV1hk3a9r2X/f7go3C2AVO7f9/u"
    "Ew5AurZKebNDgnAZH48qy/SGnkdoY78b1qqqCzQqVaKLi9vb6vTfZuxbKQh8KDwU/scZb2I4cY0K1qmpOd0YnUVuYDtcJVgH"
    "MEG87j241rBOF18h6ahNQsyR1qGtYKwImWczc9gCpQJYQDOXbZ+Rpft4JzjQ38c3YqyP3sCBY2+7P5XbeEnf9tQcI7bwZKpX"
    "K7I38N/89xL+1jevJAesAm2bzDGt08n1fMckmfxEJ7AJ/AAShfOUoZVOr28R0SH666ABMhrZeXa05XUc0fJYWs9tL/EbCQpl"
    "12a9TWpi6Isuzcwu93Dj8dlBv7r0AByA3ZPv36EcWeCx9LefQS0Xf/jc2eG8MWV2TmC8sp0/f/MvX1fF4+KQ7TfFKjymLwBe"
    "R7ApYdXr/vJ7df5YR1yo3lDkx3ymR4dowgaGxXTYgU/RPzB2dal1wGPgaFvDXSZgiCju6Di+V8+kOlX92XV6kfYGNYYAf7+3"
    "cIjRRTyq7Q03WyCiqtWj+sR/d8qYU0+3N7ynDAFfRh0SBbNwQ0f+o3Eeb1ggHRlQHDbVn4GEe0xyGB7w35roArvKv1q3YRGM"
    "HO4UE82V5xhlRKBfff0Hu7kHNHY4qaGl+BTa7tQ13FSZZEPmDPMvge+r78ya7ufuAGcNx8PzdfXkgUeTQqDh9zFEAguekYTR"
    "aevxZqyULBw++2ASJrAt3kJ0Tu4+fZSdmUc8wdiUb5ZMrBCLO/UOoi4aJhMJbLxRVPAQUZNWEEU63vkJc2Fkf+sEzFbcAv0I"
    "c6kPn21lJoLxH+/AUWadUiSrIOTNbtHE6Cs6GhFGGevDVlA4be7wNIrgym1uYrLR2Bl03TtBnG+e7rqzfcpgf+xVdmIvv/o2"
    "iEgVPxMuNTECIgE9WnyI6gu8ITe+DZYZGLZB2JB8Dra0zkJkDJmQkAwGmZ8RC1XcYOrSB6/xhvswomi0GsrNdwYXYGTj6Ko3"
    "yqPA2NSbSTP+0Bl6/i4gAAYv2cggdoFkDVVu7lgbMoPPT2zlJ04StwCOEdPnzBSmQJAHWDjigrDqBEuT2zyJAV7a2swxeL7r"
    "ze4gbOztvVB5BcUJX36cHYUHGZpW15qeZfopJ4ZpAT/fwgiBAGP8c6M/v2gABKZDOKzpwQ1OAmiY7se+HomSrABJ4CNevnqM"
    "sD/jhYImUe9YLFrV2lwNLJSNxWvsTHhqH1ztiGPLFlhPlmMfGiUpOpV8x6jEyw687QdKS4rj4HEe3grOAuLaa4/AYrP9y4Yh"
    "SVfKh6BMgn6UnNTvbqJCzzvwGOL70dBsuroVkYjG223VzekgPgtHw/CAt7kvHG7P2zqMuqqSzoGlI6iwkE6KJDLQk9FRYNGC"
    "1T86QIg2wkyPDCdFh7ro3spT4Oy4EzgQMCA2dtUZldtbBGwhBtlorK1Pt7bV1Xyn52ue/qCFJf89vSTZLnCzrahzNxw8VFJF"
    "uUXAXV3z2flZLr06+rvmcwObcZuNB+VwLbv+nh5tmQSXGL44MLyFpSBe+IwrAMziDIEY2Bg4kdAuWHUCQIImWEO1ujG5k8ej"
    "DPfOkB8h1Aq/VbGT7E7CCeTvZ1/O+E/JUf2dGcpdwfH4L+cApQh40csZsFf3OBO+IcALlcA810sfxPH/+Ox0kbR0OKmOJe/B"
    "MLyEUUKqbjGCzeqacPP7ywLywKaPPnNiSh870QRsCH6FR1ia4+ilOToiV6bZAULf4FODw8F8nk+R10MkWt4qL5CldjwmlmZy"
    "Nz/fAyxN9vUq48PHo6ps4DGctshk6hq/a66uNUggHDwy17UJf0v0cPypRJV0IrAfd+q+j1MVokve8rrGH7yDdzhg1H9ODqDC"
    "wDOnmAJaW4fLVn96w0jA8HJMXJOtCmGBJDAfjn5y1x/eULObhAXY7GA3tgvPFEBw6qtrZIe47xLS8RdPVHNijGT/xYV4lT3p"
    "ZLIrtHERZ/G2nwAEAXMNcstKbzQaiI7gCcoXuItkRohk+lPPrdxTXIYaMToc1T6oXWqg0s6lurlFBxZAiR9TDdh+wN2Z38k9"
    "n/uI9hHRAheARtyWOAXbYhTmwx4mAtWUIv3xQzMF//EMlAtXr1XC5Cr2nwgwb0DX3/j93y3BOjDSz0b5nONyu7HulokAQwlT"
    "eFaIskHUYGUNESYnNPBx5sWIFMAvEjxSuJ2nJNvdb6NDpf7okv/0ITiwlR76MyfyrFdRArS4+1/CqKGE76alj1Cm37VQBAva"
    "2HQXbpWbevrnX4F14bhlgWCZnzYhpbnd7FhXVDd3HZV2Ni5qjqpA3ylhV72iC76agZTm8ix2BEd+AvTyHLauPSXoXSMyAgx5"
    "lR18Q0UKHhPBsZIhC/4FI1ShGBUmTQ1WmkPegmMQ3XOa2xSs3vEMBEP0hLhTEHeZTODyp5YPIygCpHBnL9wjua2R3OaiAkYY"
    "rVheAYcLjsejPuq3AZqGrGuoF19Sp32wSSMHYxnqpPne0e1tAY36yuvmOeHqygCjtFXX0mLiex2PgCsEq84iPLFwJI8PGqoK"
    "pUniTlxxJ4JXEDLJ7exo5I7IR5yu4U0vQDtCOdzFAYyYfehV5AixB9K96icEQ/YP627ABDX6CYTn+1cx/Rym3s0fgTxvMsBd"
    "xRipLBjvzW5uANWCoThx/thkQr7FbblsCWtymytOGhgkzQQQSQWM0v7pXg7NJkBM/cEj1/bTUUBf9B+9pWSA56mjm2YXtmXs"
    "DcA5GqABGkqH6c+/iwr7lnR1LdyTMinFQ8Ng26fVmIcsOngX4gyTj0soMb+Mqe8CZedYe59BJ4dJm389C+PImh/TYA4U+VZE"
    "bo6C1SDcp4de3fKcpWITt7aVt/rPICKfEBon5ygBXd1SXYcBVreFXNngJQQSKa7NdcOOQ8acfH5CBoDYd9AUHIBUsyABFxQ6"
    "DWDGUbBJMLiFNYcczb4mO0EuCJKVoWjI2et4SlG6NwiXheA+opwA+JDaAGQLc8KFXfMAKcg2meZcVhYeIBi4DAJ0EWLPkN8+"
    "bOxXJH0TfxPgrbJlx7p6xb5Fguj7qlkS0z1+5E2uGI7Wt8VUkpldRUjEwOONys5mn4FQ8x09DFzPPtVsCJUWTlQ9NpOmm63p"
    "lu+r25pafjTTuWKnM0aNN788gzdN4sPYOELm2bWMi0Qg3/CXelwdE/wAr9mRuEKHfHzzoURJer2RjG4LpefYsWnRzutWU31t"
    "urahWsGvA7NqduZOOzEAAf3NmPmE+mYyX4hwOeDP8SZtWTpluglQ3JyELs1EH0FRBcfocB/cEA758BgFQ8hmpmiHBryamvfD"
    "U69nmDwwY/RN9AHzLUpvQIPdrjeyB6hHYbMr0NX9d0Sy47/+0WgUnRWjOaN0RnYJfApvGu/c5iQQwmwIIWKcn8P5YIuW+4iA"
    "cg0yeQ3Iq+xbeDK6uWn65tQWFQF82SGDgrLWF7XGwKvTCAi1NOnJUf1YPRne5gEkg4loD+9F1eePCyASGegcOWPKlRREvGS4"
    "cWCWDe9RjI4M2n1BZ1TLQBoAiPceGqsUkLSNLSubGIfoPAXyyBt4GcOBI/MqYALg6yfYts78XA/9r5j+h73ck8OP6gNXIoKn"
    "dxySRrwURC/D70ptalGwuA8fhx5HNEwO5ghTDa5R+iv7gsgBYmeq++xgyRtZJ+ZCnQVwOk6ekDkuz0TmwvgPAmRq0ixseVCB"
    "TgW9E+CpYB3ztCk/SFYNIqcmzG14sJE9ImTZ8AGRF1C9YO+EfIAnZu2RS2Q6CDK0njm4Gxlx0SwSATgBqqMcIEHbbGlqamtu"
    "agvs8LeTBAdnTqnEYhmR/TPf44C4kiVnVEub77H2Pnz3HBxsMoiu6S3/maSNbU2GLjx1pLosTTx/BgjErJmBWX+aMUP/ySLA"
    "FzDFAJQie4N/e3YVSxQzy6oB6qupV2oBv9pmiiJU7g9bAiFag1ISPfg2kB9RbsIsJNEcaYMNrJMzLQ0ZGJa2DBzIAvMhrOb5"
    "1B/viWyMPKeb6Y+OQVWzKWtQ3tRbb9I4hrfzcy/FL4MUyucx8DOCWW3NdLFqzswryh/kQR2L9qauqEfvo8cneWahdfPoPboh"
    "AxhesnBp2jsTi6CviH8p4tXof6URaTrJ3k7SHfD8CU2C4wl4AYh9+4Bo34CCbyXQOlhgrDW13QHlABqgOlvnJpxCXjd1LVL2"
    "/ImGRrNvjqK+pmBCEZ0gVNnwBpih5CBqZM742vvHkUdmU8xKGXx4shvh0NKpmQnOiViNanxS4kwtQwaxdbK4jLfdHduaWkT8"
    "A/erFTbeu31GcLbHZASdMK2iyLtgLqGediU8QRO7qmvB1FNFyd9dV68YPgMn7NhrS0/y3cN2JtqxN/YQUsKmZmkqJqwlzvDx"
    "qDo2yKl1fPP7sKgiUwKgt+lOU0tj4LDB5kJxkqQ1ja9404iGvI0qbYUTCrdGn6dcXFhUUqMxiagPEtOOrcPp4UCMExDJRY2t"
    "i3jJjZcRwIuMhtEa0SUxG0ULRpnBdz9W3wRARdQAeMwkI2UKalLumGeWVLZhrVArPYOJFOhrV6wm4K+/8pc7GfcEixvGh35y"
    "6N4Dfy2QnVDTQGSuCapdMaayMaMKGvW9D51U+QSOClAhrRfRBATqEnErN2AYLXU3byrfhceJ63iwSF/2spy0/UXjcQrtgcTz"
    "8ltHB+AuZCZUC/cfPmUAlGEb2Cd7wTymkbuxiMMSis615wqvo9fr5JRu/uNHkH4SOTpEqAi2gKIvmICzHDVrapuaWr5rZGRe"
    "HTVT78QceK05RXRLj2xG9UxnDqFOduVy6G5aF5Y8SCRkJwyuSdUFmFY59S4MduUnO9zN0J40u5iDODKQYGhjoWMgcHNQr+nv"
    "jcfrbjXdvlUtm4EfqQyJGpoX5kWZpaI/9DUlnA8r9Nn8q3UjWN7SLwMIKP0q07DzToKtwEMwk6F5da8H3pkT5tZgCh82rKMp"
    "wN4ylETxqfpLouivheHc0FxXX29g8E+mCL6BQJhAyttr5eC54018H7WdPyIyoTGiSzBSemdAHqJcaZKiZObOA+EVsmPtVfO1"
    "rBFNsoYk6WKKFtVSkSQgTzbH6PoLahgDH3InJwl+JwyrJXDN+nMnlN0H7zShi86HgdcwcKNmWvEjf9UNioGDICQ8fwgkAQEO"
    "+130V8qmsanDtYCRARR/+Cbiu5E+TSa7Kt3bU+YUgXhAhvuye5CWc1CVZiQJ5CUYZEEiJSAkte317Q2aldqTn1xBY3D7aGKj"
    "NzbgLT6LqmvJByh0RUn6u/9+lTCLrW20qSHw0GfDNLGRzYglLR1zd6DBIGVl4ZlN6WQG7wad65qDwDH1vIkraTX11T/WAErW"
    "WKswQRPrW3itEZr83K430hPV0gJsa3wiVy1PxluEi+l2BIFUOFqYcvt0EmQc7M7yCPPOEdUeNN4N7c9EA4T2EFnQhEZRgR9w"
    "WAAxqFUdm8tNuM7/dzqtEzGk3reoQJD84iMIy1zH+6ikLDqXMBO7472XmaAOsLYp8nJY3UXMnNF0BQ2cip9jAYmwCl0yDHpn"
    "B+/bg4d3FLOM8iAa//YWZ7LIG1o8pZNDPElh8pqxCTCmFthrJiv6vXc4ANsUZ9HkHwzH4jXOjEL2djWsl4AQD9LRiT8App6e"
    "caRaMtvyQ2fotI1ln4vXiT0pmfmTB+pIwGjwmmZPMMA2Eggbm4fvCM22NLQYnBrVzZCmwkzDKRQ+WBAyQ/S2swAn4sylgB1c"
    "dZTnPqasIGTRwcgqQJmE5mrgY2UhjArS6yw5rKFSY3I0EN1YYdUEqF+A+w93QXnWlyVLd9HkpiJfG+6pWJoyVc6mlmpTQESd"
    "lNAKmYWoGtqr9cDytMZA8hZZ9oYXEY9VQDs57MgQlHamwvbs0TEhKaih/kzvH3y4yOtVfiAdUw6Jm18rDqhfHbkNPN1CaNhP"
    "wOr9/QLrhoytrRrhzrbQhaukygwRsRlBsNmNjihn+/g54lsi0c6O9hVhhNaU2+SXnV3S1l0WR7+a9K12aDaziOUhNxgGn1q3"
    "Rih5RZBVrskL0Ym1oxiMsgYmtT/YVCe5Zo0hdQ2or6hVcC7xWQGL15jWzNyvHdiXnJ9kENHnHdQrKZXkOAZBGEILQp6GZ0tu"
    "Ci0azSMcfQez1PLM7BHqBUzBCIrZbE2NzRA8AnjL9n+gl32hT4s5wLkHeRAVqefOxOqgmmTjPXmAVdHwtDWwtXUNICBBzHo+"
    "TsHcIjslnYsSNGhYNIgPrOPpCNAN6tMhAWnBlkLIw626lta27+rqG/W80JfFmi6dryVGNp59Nh01QotSXaiTTr9VxYBCbagX"
    "Ocn+UL+aYuRwe1YSHR1CY4zYCM+mTXCu87VRTvdfEtUWpCKfHb6jPd35WFOqVC+KlTBobQv1slIm/Lyek3wPsdmheY0NI9Mp"
    "qmTb5JC4Uvd5aPK8fU6QgHp13s5QzkjSDz0g3essfkOA5mupBPIIzttgjqNj2bHuiHunnxsMjVXjbToiVkFQc+RFBvsl8R9x"
    "9c4/Keq4am9sQOJdura6DXMO8tXg44fP28Ajp1k0qmcoygjduUY28HM3G5/6peTCA7JBvXNnBxNgXhXcc6uhyOrObSy7G4je"
    "FOBOJLeoe+DyPIDHR/7bFb/rhXf6wUToDwah2tCw6nis3qxopYG623faapoaAeutEVqTSJ9IrrcngR2+662OR/2LRSf3Rehc"
    "wPuQlTC4hM+a8KPsq+VOCPuGcUiWIIC2GviAyUWQTSrZjYpAzY4Mwq63CFRdN3LGjT6pvbJQhEybMEDjQw3Bh4drKC7mzb+V"
    "+OEqlMooz3cnGMqxz0OOv4ZQ6AYzBo5PFcLJgzMwQH89KjvBcT/zUptGHaiQU1IrcWlUdNkczeFDKl89YfEcHZ3CDI0bZXY1"
    "bhumG5rbfqxpabrbGKq36upTd6Coxc+MrRvyTHdyBUzz89DRBcu1p5tqgkCLVO6Qs0tUyn/SqYYW2nVUK7zjqLxagQTaoVYg"
    "Yer58TChPFqwQ1WUQSbZ8oG5DSJ+4G+1GKVKUyPsVwBDl9U01aZTJQTYp0q4qz+mUFetsbaObCRV8n11fTt/SNe0pNvKHYj5"
    "raaWEvfV7+oaa1MlMFfq2tACPLiJzWj72lpJXWNJCMyudMoufNLeDL6QLruHPaj4tPJaCf9/pVL6xMfoi/fL3QS4xFevFn/V"
    "ZnXZFzX/wDhdYukv/vPHBFaj3MfSTGKWE38TQPtzIkaQ7axJX/2DyE3mXgASZAVI0VyneP7P5wX5P5ISVJ/+XkD8/Bzk/9h8"
    "JZcAI3lacFNNrqOoH+lWgVvxSYiDjUjDlW16Y0S7QRFBgpEP16R+zibNk82MwnworFEdUHISndxnO7/PkhMTYpO8UjhJJlDa"
    "SV5NmmTAIyOJNEDedm5q5nOR1Cy4Vd6jUlyHtTs0Pz17+OJnTPPzj6asXS2c4tUr50wR1JlItdekI0u4FaTwzyorK/Tlyk+q"
    "m+lmKNMDUM6EDWUBWjqSCoA4mMlHgfYi1q+Tc5U6jywmubPMiUqKtqzHMNMqUFtt/zFFPeJrHwYl/3ZFS0kyvyKs6fGrML/i"
    "ZrXxE3qQxnPr/mi/olU06zlSHUPrMmjsLqkog1OagsYSmnnXL1CtPs1HYkplZpfpFGNMQKQGuP4+VpshyCU3ErodFrLaX4/p"
    "7oKYG5Uw1QCw0q/NyKSsRKTeCEsvSHwBNjWRZZF0f0mMh7QKcvyZ089/ASk5zlA57pjyuwbyPY9yW53B4JLKRVz+LIxUtjT9"
    "e7qGlFvXqlUjJEMGhpiWXFNwHEWHZvVrvQVTY2R/UFULDNqWl4oMl4UJNneoDMCNhaSD+XcGM87KjIOkl7E3JmejWCGRy2FR"
    "iNvQBtKNphrKk0Gemf0XcE0JDhF+6M6gllxQeUD1gqQ6AzI0BDsA2VEUPENDQ910lgVFExl/CEq2VThFKtwKIUz6bAiokJUq"
    "hqcwU61UgQge0o68oWfhsqm/iqslPC+7nYmvFquYTK6TnS+thxoTsAFIAVyZZgrhjJwr1AN7PFlY38BYipX04IW6VN1NSk3j"
    "jIavRIQIosjwzrCtFz2Rig1Ua8R+DfcW5cHGetSdk0CQzPGHg1zyqHSJYS4yVoB9xvnZmcF0CnfYeIe4oF/YoX5f14RcPkOJ"
    "2bEd4KKody4hLbHTZCvQYAhqZuiqKq0kLiahGDbXCBtKXUg2l/j3I6hD743vRE5KSHPh+SB/RQHWtjtaPmqL+zf0gGWyREXk"
    "+k12mk22FWzUcmLumLj3MbQ46RHgcNTBV59vEWINVxzOCQCLwNNKPdBgUKER5lSsCIvr3Eq3tPzYoFtLTRQo3r4DWCCC2evx"
    "95dMjRp7bBV4oeZOwmm1SbEGUba3x8XqfYZqefSsvZuLVQvhaD4PgcI1qLPU2Fat5i8ZFTZsiulzLKYJTM+CVCFiYbIlh+CU"
    "sGL7x/o4CuCGXi24Em7k6RxgQvne3tzOWwHI96gTN1ZeJrZGqL5iSIrVSuVkE7jw9pEiGLypnrAqTsg1+qaVdRZlH1q+h/mA"
    "Ad2LRTBM5gjUTt9WiD9wOEi0Soyzdq0A8jQ2NRj2JsFZt06ValTQwYOFAxBdLIOEhZNal5M4a6g3J5oF3XYMbwTWAGWFk0Bj"
    "GYkt93LlswiS3fI4xXur7wIsOP+oX4HnETantCFCgV7ThJNJvjC+b0r3rTwUy3iYWHBNw9ImD6eSymWJHzbKhmtMQr2WumHx"
    "pe2VrKCfIPBDNQC7a+S+yFjIwqSlC3z8Wr8kL5Fl9RsBQohAkdfboQUCCyszJQvYpqDGAX09Aw+U/+R7++FeNMGMeP0rmGrA"
    "oyNCKS2DbvydTMJZ1XRCxCs0cE4MOFx2GVZYSdBMvnBG1BKMCL4+qBzgRRLIBCjKW3kd7qPyHnsQEtgY8axMBDd4Vv2ZtQGB"
    "qEE6YMdTEHEhJ0usktTUcrs64Pz+0SQqQiJbQSLGskzPR8D2zV6SnpFcksj2lfq1SCRS3Bi4BnsdfU+ROv3QxRW6DP/KZSfF"
    "qQXarVkg1h8/7c1t7OMtJhYt9Wj+riF3ZRl2mYpLdXC8zSm6ROnW5xpxgyU0rdY+vGfwCxWuVCjPHX52l1nWLeohnNZogsRO"
    "eg0hBboGTwpHVYxL+ANvTOHblZcmnRVDkkpmdIMDVHV4WljiyuERV5z0irr6u00NVsXQGpKELh2/UVQpHGN5oONV0TAFyAL9"
    "wkijGHlhhCoKtYqlqYNLhtsrSTxLUOs5b9HME/SLUEA5hxFaUFNbu9EhGUYbY/afok95Ara6oMUGZOZoF+ftLoid4lxqLKne"
    "p/yMiaYAUEl5vRjJRVW1q46zufWOzVHJbx9lNyc0W17rXwoWfDIsO4cVsLzWqhoFw9O3wSMmXmhxPzillL+iSijOri3s6jLa"
    "WH2sIJgJnBmCs2b5uobIbju3QICav8vxQR2feBEqRC4bMfyskBLBK4j+k+wTAiX3NsI6aBsv6Rbb6Ee8KSaDIwclZHSOXKiu"
    "r69Dbf1ms6bASCJKAxOPYXZoJkMmHEzlBDZ6RFOytJmonEjdR7lMQMwZOhAR2AbgqGdO1RWszbkq72/dCo/wA5rznJmj9FrU"
    "wAuTNlCzG/q5+gbDk2PFWDJjlqKOGT0YJlgikErCqxcGNbIFRTMoTpZUXTDKceBlNoWPodIBSQp2AjzGAjMMDBBtpju6fJYq"
    "ZYeSWSINHSnACy6r9E2dScprRLJPY4SZVCZT81JDLUUUgdzCA6SHYt4SdNhFbmkwRjERyT4CLSC+fJIhtsnYWeeGZszAYKDj"
    "F8xSy1oDcyfOACKbDjesjhdqAI5mJ06kQLRJViRTAAEx6pe1U0+Sa17bE1OU+mj4SlybtIY0OgSQBEpv7tAYmIWvuvCUhATo"
    "mIetyEYO4FYUuKYUtTAvEU1DRumM8UNTVbRw8RiZOh6BYeNNHCnDgTqF18gVgSABYxMLwx88pTsaJWeCpAyXPZpTw5X8hwgd"
    "1gr4QIY7vMzgIEKTuhKTH6ApoyC+KRwfHJWPmdzUDLqGVKVlGQPY7FjcuUf+h24DjlzoO8/Sds4yHGMt0B3qTNqnoilWXuaX"
    "WeMUU9YqnN7Jo5B/26OcPD5ZTsnqhrpsS7SfzlJ7l3qzBuK/31l4lMMh/kMEWmt5jff2JSE5Q+N0Tgl+1d9EgaJ34erZcqBF"
    "GQ2EH0oxQlCb0N/WNGKWPCkoWCmEFJV/YZzUYTShgLlVHQyP1UohXID8soWo+3bN2GIKjh1bwSGxiVGTJy6CGek04IA2ma5I"
    "Ac9QjtQipmulcq7vCYQn745hapBJesKXoWUmuxqMLVBS4+vGOxMWWUGBSjcW7TS8KwCihFcWhI4JZ3ihiyLkzrfTTY6Q476i"
    "DiQw4uPHjOUydQJXJsxG/XfWQktUDlVrMJxeUj7IxCczam+z1vFKtzM+xzwLlcOrzvUJ6e9wd07Amo+zh9vGgFx4B8ycJMxm"
    "wKwjIs4a4ckuFKwgYNyiwL3hCCd2rQar5Ij2sicrNKLeLSlSs9AOd3Scz6OR1dvtQeARdwdBIiNNcKPPwIIgqYYdI8keEeUN"
    "CUup1T2paYYFloFcIYvVCB3OXuH5MKwmqr8iBesmwmBpAxmRcgKyS+T4WnlFY86qwRo9O9hsy7ELWMy+VNtAEsLRM3AT1h9F"
    "QBKlyZZWTQ7VyUHhZieyaEmrugnEqDkwsL9GpEYL9K33S7aefMRfEC5hQI0JrhYU8zdO+AUBvG0c+LMT6oTWah0RFEBsLUOy"
    "dHQGuvZqkDsF97cpNSyyGb5pXlck9jZrLap3SG3O5D3WItoaKjWlX5GWc9CtDlwNgmthbvUOIZ8jJlBiHhcG1dqQCmWODA3F"
    "VX/nSW7jHfEqh4NagTpZYS3qDZXrKgY1v9tUJh1CPvcu3ZS4yWRxOb+86Ja2K+KO/9TNQYXR1xLoXH3YmWGwavSAaWr2GQ82"
    "OJHapUYgi1Q6z+qjjhpU7lblmvmXY/uMQ3QvFxbvdiy9Lx0AAar+SWxcmLZcS5DtMfWbAFbgbu3MsGK09b64fDvZVDHl3sUz"
    "RL8aEuAE5wCRx5suJBPO0WYcozkpQtTW9KNeDWadMRBJAKkjYYPJ44vzWiGdiO6IQapeyXM4I0UAAktHK9Y8dt1YgHcC7epI"
    "vzBC5DDE37ogtdo61D6yLJxeqo0l1ONkAvehlGvcWCK81DXurd6V7GkjPaJcw8qr/Ox7IrnHQoQcirYhMGi80DAGV55KMeun"
    "hTpYqG276izAguFYEUSEmojDopAN7tXogtezEBzp/hOTkpfoRmI1vx66aJjAuNhhbr9ALolg+hC+zu2sJgSIvojUmYHyX29l"
    "yeo01RjU+ZYqM6IPUgdz7Hl7jov63KBAS+xUjU3Nn8KZ1vifSf8UnFrCObbqzW9dbtOYrmkPvJSsyb887k/3Kqoy6tgNBpfs"
    "bKAkOZX7SMSxa5IVcIjlmhAmjA8t2Atm9EqSwiGGNOj6lwSqK+G20MJjHiDyucSGkjwZc5OgUXSUYRfTb+ByQO1tgGqNMg1u"
    "SCx0L+uTwGsxOKyj1JzrBP/45246AcOngRNaffaq+3IA4wMakcYHmPEJNryVKQU2fMcjg10WrqxGLV3byzORogAxrT/UG5wx"
    "1t1uBKcJ3Jp0ciPJ+pAkpJXN2eBRT2SzrRFa9ART6HVu6vVGBJ4E8i0sHu5UKnXtUMdM/rKg3GDo3gQpohgg5ScKgKMqoAT3"
    "McaYLyRg2YEBVWDMS6V/3nSEEg0gwiNi0Ux8Elknxxmt8AhfaALjTjLzrNIQHu3JR+aeHNVnt8ZBWc5SCk2fp267cTe4aVRt"
    "IvfbGrXLZ1OFQjJ0btmoq71bdyttQKomEiK3/XFrUX1m8qn3sscBRARSxPK/BB+I1k/lbWnBPYiC+n5urogKlUIHZBCyQcdu"
    "/7E5fRe4rUjUoX9CPcPEysFzluwZLup92xzlCdZibeJ60z3lJVBD/apiE6sI3d2JDp4ffGYl41ByUBx3zCGHFjqm1hZmqJAw"
    "g0zk3g9rqBSlP6j9PCkiiAmdgzRTAJ3EAGAEJQYJE0P5LJLRYv01zBFePbL3wrBoJCXyYZLzuphxEmRfbZjSRUi3w2VoB6wU"
    "ke8aR1Vi1gYLT4bjvw411zB4cqu9pbGurb0lXYvkEMOpWdFrWtGTLPCzQq8KlOqIF7vQRZzgVALelynfQMpIreQzwDInw/sw"
    "ct0nIcK+mHPYsUrhSwIqqvlOU5trPVO4yu2BvG7uCN4frX4j6dwRm+p8ScgTLYFE2srrS9n3A2B5RIaAQnsYttZ8/AtKP8K7"
    "2hvqQrqEWtK/Bled5IGMUrMVBG2Sb6SY/4FBC9jKSpSQVHANB/Y9YT19T9QLi6pYDgtKckQ41NnSVO0eINRLm0IUe4+X3M10"
    "AxmmjmKt15UQPrMGQRJzFLQFPHH0ZwfAZImmDQNEYa5wdUC7Ea+ntQ8cG4vQYhTQqa9uaTOeWfpzcM0TBBr4BkqTPJgGM4kv"
    "rDVVi3o/DXwHBUsmXqAMoHJ1c7vEg7eIlhSap44hHcEWAduBykWhyH73njknAMch7VuiA97auLc+G0dSFD3uElGTWJpmUAYR"
    "DFAl/MYYNUlA7sXw3y87wb8wkctRLn7rVoi45UKzqGqj9uLSrjJMTXSLyMMYwiLJ4Bcslq0woYBCvf/Rpw9+MHa1ahF4xRd6"
    "tYtWecaS9R/4GwMKUyRfMncHSVrs5gGKRwaXqq78xsVhWtAm9Ry5WI8VYzc43Et//eev/3Djqz9VuZeO3QuuntAURrOJvFiD"
    "hxdWw9ixZg3SqfROgE0jPd6GbGQ891F9/YbeF95Qi5GMAy3JorWe2NJIj4Mw16QV1oiSXjVlRQMENvlQkXeGuKNZimL7iOYl"
    "pWygHaM6+Ic9SliEDSX2SujIgXvrpOYEIrhaLXjgMiFYsHtJx8PNxsjIE38AcE6B4yKSRajHHG4cBBDpsf2wYeasN+1kejS3"
    "z+1RPHWt6btmbbUmlWbKhUl8yK9TAz+e7aduL6Ngo/bj5qSNsTKmDqtAi6gGvTGp7k4dXTNE0pnNZPra/mYOdBTk1pm5RVPw"
    "DFIChqNEVRQeZ8LGC1umxBrL8G5FVrSJqxnEjuTWFsHlabIZ897eS+rLRh+S00y/0VQ5ZUdaMEVrtYY+cEk0cLtrZcIMemsM"
    "eqMbAZaH2Og8FUcv9J4JIwjd5DXdPKlOn93YtuVdXFSIPzCFPt0OmTLWUN1qrrVRqIXNGcu+HUeGlukqklxmTHMplMth9WWM"
    "5+0pr4ewDjfVCt3+mMRlxJNckIN1C/IIWV4WuVyS1GVWMpL3pWa3mtqSwTig7maSSf+sWdf5ZTTgdsgkFqYotIuDUUhG0q14"
    "Z0XHkcKBmX0VXJ0YycyiBj54GtyU/szUx830aTGx8H7eoDNJc2LdoQZDntg+m+JElcCW/NE7D5XdJCRJTesDtqQcoDemRk+w"
    "p6gcFq3gZo4iMPA305bPicOcmVqoZbuxpNlIWl8X/EjuQonnMCkSQD0YjAtmnivyxtZfdbs02UHMiTFLm5AihBptKNhodjSW"
    "U8SZBjkyms9qihA9AePYiNQhCvqUlB1E+AByrAk4OnBlIFsnBYbLF+TLsJ9oso+qsor7lg9dWGgLx2P5lcyI6fK+oPNr6pD1"
    "UqYpMJoOU4NMl3Ii9gtkzycwsRpay8oVwI/PzfXQIiCRGnGFBfH6bpaKZujU3SpRHH/J9evSvqbghE0asH+ZjEOHcYuhh+z6"
    "oMrPv3UM3Qu6qrhcef9vHcOCnN/loTGXEQ2bxNLM86JXYeCfGknhqQjTdCo4oEoIctv+Z5Ulv6LToDy8r80mBJRqiY2gLhdd"
    "L1LWbx0sCdEDUwFj/51zJwc0mtUjBqPmTghUzLw3qaaLq5yCvRUb+yQONVMCWMBlBXeeaUkOzeFh0BNKPqrqwBaXMI83RgvV"
    "XE4ED/Tpa8aapQoZQbunC4HuIxeqIU2Xjp6ABsM7cEefsxWpBAORDqHFqYZQjuj1aQLHn96iDftqkWhVmJqKZETeclAzwH82"
    "7uu176zrFKhgWsgIoLXQlB7bcUvQa0hfK73Tf6J3eggGyhmJcYq8mglgKDtI/fQHx/Q6N+9ok5FireE3vcV6p+AP4l23dZln"
    "NAkCamBu5yV5MMJ5uOBuw5SaRNEv/OSPPjJX6B0tuvvSj2g+cT1husH0IsYg81jU0rYclXrAePVOj+sHKg0vsxZoAUpGkhIm"
    "hsM7QuBt6JjCLZ1IuTBgZaf2bfR2PTIEub6H8DjZSXOf9Uo3LAVkseodRlIBoI++l+hFKYEKD6tMLBS5cfgVI71zr7GC1Isf"
    "A4nWb8OguZN1hEHteIKsMPcyPPY+sMqKiyMdmq4I3ZJantCJYiWhTGn5WC3nCc8zXgkGgyKDorswO6H7vUFj9/dKFbCXpo4U"
    "CoYJRCYoI2xIVPyDenCyma6zA+SXDGh+MFDwgrSRK19xQ0Dfa73BlR6AIYJF8F+bUVBqruMh6OpALQYsAsJE+BdcGMvKzRYu"
    "ZGwIoVilBnsVn15MFUvQq4csreLVtbdjWXrAga7NB4mwBRdI9b9mFFJy1YNLNyVZRy6v0hf9zGNyBwG/xK6Rsjc4UXmvYj1E"
    "vesuniRo0rWFWt3uc4fvVL1nTc7FAZp7UvWUwPn5US1ixLs6BdBu485FbpFi97eq7H17To5fcGGCQCaXsytHsTu09L4fUaX5"
    "JLCtojmEt2ch6GjKjm0t499il2k1QPTgkqbqu41weiUsAxV+ybuO3amV3dwjRxajVp/hkVM6PhpVLqorRBIXdmoYHWy7h6fn"
    "r0o9dEgMp4p1hKI3tvGeLgSKTLk8jR1ERgaDCokUcN92s4qGPq8RY9LK3GOROgA8bugVBubW0T1xzMDNbgtSREYWSfGz6Zn1"
    "tVWmPmjsIrJVc5eZ3L2MC7wi5CNrwoQeECe2UYrdkyPojWsg2mNakDA+Wa6MHLgfW2qbim3jVTeHNBiY+t3quYA11a3x2w27"
    "VUFlkj4MnY3Y3Wz8Nbe5px4krwfi57Gi8DAleyEZnN1SLYJhAnBAgK8kQrlNInS9IWF266Wfcm3Z1fDaMtORMJeD3YKLy66K"
    "FdFYW0WtDH9/29KeLnKJVtLNWYpt0JWAFUw+9viB3C2xCliCe3HWxy7mKm1qh54dXKMo1fIhX4KGcUQhPOHjgXvBKqKou8P4"
    "bIBp5h0BveNyrZ69QI1unyr1+0Q3ES7ppV3E+cR9ANP9NHLdnCgWTH1E6FKeJHnLkz4u5qKzBdXXNsww6fEdNuXv+npw0wJd"
    "SgsIPG9H9cjIxoFrNZ9z2xwzoFDzaA9hn6eRLOmCY3Xpwqtq5syrlAbVotSZS6UYmTAWHIW9Jg7D2oQSvVX3lpbKcG4tvAh9"
    "6HW+JldR9ufn0UR2dVEddiiBAI+SOOjGlOrIjYCIlU70siHMxLgPQoK42YQ6+HfBrutp2EUFRsdTZXAqdSIEIZcZS9Y4dQ/y"
    "kk5RkxZXCfZnmaoX3pPXKkshb4lm+Onbfzm2/dpN5DbUOL//Cduvc9C5meCEBEVF0QxtA295ThF+DF1BJlvR9xN2nXj4YIkA"
    "ReZBGnjiv5/6eXtPAD5CvLgzAL5/JMHJ9TO63+6eqPdYLBuxXzd28brirkw0w2EP9O5V1TV+z52JJdC/510s4nkTjNULpM1G"
    "GD3MLGT8gQYeMsSjQsbwXIA5PmwFVzYP8uI6VN07fBpUpE0miYTLDwEMoY4rb1LqnsxcTbz1MCLOftK6smXeKDP/xJ0ASSIY"
    "PcJsiFrJxUs9CszR/LIQxvbTxYV0KyWrRzRt9+cLCp3JUHDZVmYc6pRkuFD+kgaDxGb4QRXZGKWEZlx11VJF5HFUW5Kqut7R"
    "FEyTmJJEuJ/+2rmg6Sssay9ON5bq3ZoG4k8iAf1W6od4vaHunyfgHUkxOk1Yg7RZeC3pz5Tu8/AYdZpyxi8y0Qs9f9JGmTZQ"
    "uFa0RdQoNuS00CelJQf0inRj7grMG3vLmAA00FPUzB+Ibhc1x/QPd+pu1hVcYUvdUFFR21O5tb5CzZFhKATlBLSmNUnInfrG"
    "9BUq3dDeRA4G9UiPWUvj3cEFtyyRt4cHV9syFpmjhUUY+9WfwNh1nqzG0Lel2RFcUtDEhqmtZQ0snRUvs+cdmwjMGOieqocR"
    "bOpP4fZQVBA16JYC46MPvIFnP/M4y027+Qcd2AdLHOxBPZci2kHvKE1sHDZWYQ7pg2YPKo7gFruYVUi7Um7Cg4FDD/NQd+RY"
    "wwB+PctIr169LA8AXSIo+DX4QdXM0FtoE5V81bdjlHL1px3uz0NaEY9ykt7++c872XQ7zD/R+YnwDGXpz9s81Sz8/hHcz2Wb"
    "17WmMiBRQil5mQkCm4O2kp/dQtR8uXSphiDtkhtAMd2urv9Kqn+Uff0DFwyfjPeYVzPh0dr0rZKqRoRe0i1lDC6lSn6Jy6Xb"
    "Ws1TqLIEyAfcyW1ld3B9A0pNfIIS+1c+/6Ks9FrpJ/8OyVkGzHoZgpFwYkfeLy//JN1I/24ZPt1J/1BbdxsXC5aVS9Q26Lim"
    "urm6BvWeymL9fQYvcGsFU9Obq5QSKkt+WXJFvwXBtVTbV0srg8aYHiZ7WtYq9aOqtXJUa3V9WzBn1Lfh/b0clq0/RV95WAsn"
    "eM9Ww4lsI7zpUiXqxtd/rXBqRhk/NitM/f56fODawt20hFDY+3ktXMY844SDFf6hDPprfEF+XXKlnCMqaIYzKnMLFdrCYuUl"
    "6frWdMnl8ngf7mJw3jpo3jyCEVv6qJD4IyPvXFQZEde7SqpCgFtUlpf8PyWt7Q1lZrbaTVjoS79mH/+7rrmM/QTfBftvFlk6"
    "/r357VpksLzt6Tv7jTz46+vmSfm66oK1yP6esEnBhBmduOxS7r3SOl5Gf6v0Ht+6X3WvteIX7iu/qLyvXEIUVl2WgMPKsCOT"
    "1VQB/GTmUmonIy/biZXKzPCdzjDaBipGNTOpl+P6p2rsf4qx0kb+GQ/FaL1onqprhWQVaxaB8tsCQAiPWqmuLL77CzDH+LvK"
    "fqEf7tuDrxBLnlSujtl9ocDr8k2FLpHSocRqS3QjSoBB4D61VgQ4Ta6GPoddk0dDiok9Zc5HAOEIJUvSdugw5I/KVLgV+rX+"
    "FV8Ts6z6iPwRWVL93vxZGQShq2qrZYsrSvkh3qQ+EqyxbcSsfqXQBCjL2DIt4A1Al9QGW2Dbuh9dElo8QrxXLhVdpgrTskPk"
    "pP/G78FVZPJB7FB20D0EMmZs9V+//epfvq36p/8F+qr6842/pEoiX3z1b9iIyyxO+UXkyT/eQNTveknZrVLCKQBiRrYqshDn"
    "MtRpxzbhusp94CWZ1+7F2r//63uxDu6XaJ1NQU/uADJAOZks6f/P42f/uT9awnIvCjk97c4vZbKT22fHz8ztv4Bb4Zahkb3/"
    "0zGJf6nDAOIhoadUThzSfAJR0ONneAjecDiIvW7Wgs2/2irSa5mpc4wn4XnFVRK8DqOTXx4O6ZcsVXI8XJ4iFnFhHev16y++"
    "KGHh6cejRHQRBGBAsqkifdC1I4XWEILJbfZjeCxesEQoA9VOIIc0Ij+yh3Gy96PpfMczosyGxvMd/Q7QwpzexvRdOAYb0hD4"
    "1W2t5KfpWnOCcQKBbdIfykv+G/Y3PIsIeUD2/Cs51Ne8UbHM3jdK1brk+08/uVoiUUyt08OIWslXN0oMntAw4MjZLW2+oy7m"
    "UjI4hhAMREYYDpWRUhkJmRRQL2ZY/BZy1EJF5FuwekfT1BN5WZ6su9VWxZy8H2LugssFHkVH53MltTYU01q0rfAwsWQfv3Cl"
    "S7xFjsQ97ApXsu8iiyf84y6SMuvNX44G3d7CBOaq20BGqrdpJbfZYwzrvT1rEaT0mglTd7j/AHD0fP+O635p4S3RErMJRArh"
    "F4inpWu+a8YKtRVwIJfDQKG+zzVpNFNtDb7Rgof0MRqGx18q9J4pdyIOPwwuoSolL2LYIc01DWWQ/Omsm7saWL8GWWjzbPBN"
    "ZJntl8z20YE6A+GsW9obC6dLO6qt6hayq1qrzNCMsZHCz4AsIkNju+MaSkkZzjGy53K3lGF4vDBKkgrHYB09vhTycuosdZSE"
    "LQxhll11NChXvEbV4mCxbunw7tXdLy3Xk1WFq9fvNlYFky1rjXB0ayoUPBXTrFXb47AsxCSuQVPYRJa08pPb6bayGh5BLG65"
    "/IVSca11bYQsfVoOTRC83MJgqv71xl9vfBttFvUhSqSFQD0oxG1iXHEN+v+9XnK13KoOfJPziGoPAY1Qa+AOh+xMVkb+bExW"
    "ksOXU5FJG7GasiJfl9pB4LSk/6MdByxlIDN3UXENm3cTzA49cYwVjdC0yWn5R3mgrd8tuZ60uq3pNuxddXt9W5kdvXRmlFX5"
    "HFFCeb5lBPjCjqW0RnXMmgIVk9TenK6pE6aC1hI34ELqDloyG69nj3kGwee2lnY1re+XB/OtCJ6O6ijxlU78UXb0v24FCoYf"
    "GR5BjtU/VNkfE+iZHAw8DTwxfU506iILXeTNKiGjQBbKH5SFVTfba2+Ljk4786ohs1+BqH/zm5IvQWafwdK8jC9kQroJleX3"
    "g1NTbBRFTlFFaZWRcdTusQMFL1agRRrCAcdpbr9ZX1ejHMyxFQJ767v0j9dKaiHLa5qafywT+6dcmBB+MBYfx8c3A/hccNjx"
    "xCfCBlvvogBkWWlVaTkNFLsvgSJaKm6ZQZamXDm8Bmy5xGZesShG4P0DSA4sHFgWoONUPWQpFLi1DpH8NGuqySO3PXheql2X"
    "MH1y40OS3sZijyxGo6FElIGWvHApZz6M/1J1Q9KlYjmlBq8/CgjZFqO5QwtMf0TexcQrUQ1XMLCUDg6AHoLhBOKOrJzfJXWM"
    "ifIZjRJvSqlBeTeFCSFYU8KM8CrRRUo4DxiXDXVwNrH8/8ZymfgxXxBPvnNQnqJsEycVS+DLsrlqZLCzBcIkKiNAJXWtwnqv"
    "xXhvyI+/r0uT9ykx6J4XkkCkzQvRQtB0BVQt4SPXSyLE4RIinwsmZpWXuF+rws7AMB4ZYcB48Jpjb0aLTstv7leVoa9RfpPP"
    "LjeNFY+Wh9yvKg2PQ356bVW0qrR25nwVade+FKi3eFxltn4BD1954TjSZrpmJxIUvdjgg/5Vm4dT6RzrP+K/ktGr8y4yjurv"
    "AYUmdr7qJzYO5eIjzlz7z0/2Dl604WITDO16S/D4OeLTDEhdnrRsVdViUm2oxKmWqkpEVJu2SlLwzEePpLyHphR7V2HeC7wi"
    "2p5x6FNxrLwUmYP+wmlIOxXW918ZxUDzH9iAVQCrNNChhw0s00eVIkM/f3mJtm2coxo+4EULGBl0YP4qlmvEw0HV03VSh+qT"
    "DifwgLin+Ze/1B+LBwBCSlQ9KHDHQB3VV4PTLGptML375Ql+RrusdapxGk5iFs3yEhOkMV/LX8I/bEDFfLL+OYkcVFXXRLkY"
    "GbOua5JxU15ADBWM07CJKhksFOO2KudNMdqqUfPLhHQajNEVdwbdv1/pyIXA8qz8aHctaW5uFY9btKtogzFK/2izWKum1rR5"
    "PNJusv9FT5q8W9ib3TndATwTPZkO5d9PCFLFh1bPkeEUVTXqnY6FczZ7WnI9IowirYQi/pzp4QJM3qwK+/+bP9wIPBfBNtfX"
    "/0ZLn/wGHgdgbvFXzY9IliqBVw2epxQrCKhm1NEfSxdAoeTvuD7NLboc0pp5j1dZixvvdwbWoo4ryXOMN+N6CFprEMWDkQz3"
    "Eu466QeUG7eYsji3FAYowahjLwf+EX0+BZ/bp9DDfoe6QbxyEqVgRjezC53ZqVWTvcRp//mbb/5HTPcuNRoO0JDpSHNfSnPI"
    "LssD2IhcJiChkRU98pJAH3eb4wTd3qj70nqRjamw8zaQUuyHyV37MeI4LsX84ivgbKe+abZAYrMXXtp4qzi7uFREMVWLT3I7"
    "T3U7U97Ya7g6mTGV2cEFCor30Jiqia8enpYWhkaaq2QQvzB9I0HvDXBL76Sk/VY28/AaPJW/4QWYv5Ez9TvvxQOwyPTd0hI8"
    "gvXhx5TekFn5u18U49e/0K3GVkHjj76VKjXH+HcVlSXUfeef0YF8OO8/66XzppOXQqS8k276UQcB/B1kvhzSwzoXfnHOPp97"
    "jFNGjhsGVt34YxnFWqi7JKlWgWSNKAYOwzZcIZRnkfEYtdHue5RvO+QQ0XzvRyWW6cJIGL1eJl12q72+njKhTeJy1eSTZlhk"
    "UeGvll/rM8501cNbeZ6fGdeCZZ8iD+ct7BDjSNaTmexNJpeWj6KGR70Vxg9LKfXHG/8ExUb0udBHXBlxtxpXcSjj4y5jkWf2"
    "78pUzHEcUxbdpkNHsqugxH3Khdaz+g3xySyfo+2c4ykW28n5RicSuIBdqRz3jUY8wtZOb60o+NVV1l3XbIKZmOCUtS2ro7/Q"
    "CSZmIPTG8qRuqqK+abDQdgnkGY0w1hb7b0Pubr15wrouylMfVefVIwSJ0CDwqyQ/0MfbwImqC02XqB8MSuTHnKUXNDdMQPy8"
    "tXQ94RLWVPuxImLdBsgZ+T/lJTJfrOnI/xebsV1kmaVETRmOJxuT8ek3JmYfXN9lx1a01WBz7doFAdlI4+HkHVPQmfmlousm"
    "sy4zs1VgQkonKlmdgYkYGDLuibFRG/egmC8rK3795TWhvSDQ4z6k3wXPuHGaGh7aMFTkvhR8i9e+0Kb/HbivRmj+Lnm7D5YX"
    "jecUnBln2eIHRjAWxQ+LG8XmJoHq6s1OBT9Ull9ol4p3gUUxzo5CzpHYVITWo4Gr+NSdXwumrubw3zcwt90iA3PDZhFhHFXb"
    "yH6Dv1z6i4fQorZIKhLuKuDl/DogkPtRW9WwcJHktFrlz7iuDEQ5frYP3UMGSr1aAGG0VsVOewMea29o0GNQaHb9HULb6vyF"
    "kq6w+US5HnOhJZ2CwpY+suCFL8hKy0PCaEktPwYWvRwJ+cYcCud8X71WWWBAlkasfIkVByaxqj9kiHSh8NaC2lLFjhW4BmJt"
    "3q2uoyJA7dVt0eoHJg53Tg8VRusxW45xG53RTKcKFc1r0oxmVt/CYQDG6D+Myoig6uwJfPQeLosDnh3l96CG4/69UWTOrue7"
    "1lGehKnIKKdyOpNCWBs1KZh6jcjqAYtQshrU6FvAZVn4xaHfZJZpO79mPzF3/VO5Mi/wA9/mMEGEUG5Jbwi80jhjwvsP+ONm"
    "GquUpstI0AGB4uv0YhVyJ66c/o8kxsy+rboqPVqiN11bw1DHELZovEM6JqXoqlpkplZH3VO/NuONQiVC9dV9x1Vqwxcvuy+e"
    "o1k62p9d+wQ1sNyunGE6duE5lSoxUcrUUEmpVEaEq66hPQghaWQAAVV5RBxbeKo8MDVM4KBVbA36NTXKLJYHSBB8imRoLyZt"
    "ER8if71MPy83SH5DWAE+ezBqfhsdQGitRLG6QA9iIPdLAEBCRbTLQF3fMy/eh5FbGjGrIn0kD1tOlThmzfLgkTqmQlfR00MK"
    "1RUwoxLyiC6LIR27NPqIscHoADp/PsYA07MGhAPqBcXbEq8sXT2lykoZVILPliv+sVhQUodEU6HqmUaxRjd5YfiJFKaTKBQL"
    "PmVYpc/fmwXyBZgnTXHlRZaoKI6sWHgQkPSZOTTDTCIoJWBerXzOM64DCOUcP7WzdhdXHEjlBZSmj1TozxbYIG6mCy03K550"
    "dZ+70KFTSP10+p246lx3rpiLBi4rVuQ5RiR7UogiHZvk7+5UA7cSzy4nWu6ifrXB+P4WnSUwd/T6iB9Rb93W8GpppFFDzdfV"
    "kVgabVecjDFSj/gfy+PgFZa6LJPf7IbBeOXJ17Zwxj+9ViC2E8fvdlSicEOcduvjjG+cTCFw6IVdBHpcbBaOryai7EXWJsbK"
    "HMy84Wa28fO9SxfbLF4aJr5BPXXGQ2h5tnidGff4CEOqMMyo8kLLY7hkCPC/0CJVBhGYwj7MkSno4XLho+3NtzUxseDZT5HN"
    "kBQINL9/ijX5Rwz5f1Z9+/W/fRtWnLPHrIqOMQHwSTIPrqtEilLZvcb7v7kHZ9B9OBkBGN2bFY/kE6arBuX3iFhFeZXeQ8vq"
    "ysx5L7c8r8yMu9wkL0rVTd7fZ5ilLfKhS4E9Q/GedFvaJDSx2J7USmFNUKRVoaLM6nEZKrrwevXDF1d/gxqIeg0q2mQJYFNQ"
    "/ZILVrcTzM/1eX0zGIPOUcpImi6YOSi/pnjxwqMVpkdKhRG0qz847cpSGyFqUm6YpSYD1WnrWJHDhEKAzos4He23btVJLkVV"
    "oPiXBjf0snC5QIY7tNwXMqxxL3SZYljvkYbu24yklEIr7kkj4dflkRW1/nFidDvlZuGRjL5oK0UTvXE8gto+gPLmNk6k2INx"
    "kpeYFtBXB0vQqgAEjHrPVEOxEb6b4tKlzArPGzRSfhvFLISEWCG/Vn4C5t9Q3VbWeD0hYIrQbXXz9YhL8kK+Jy7V9UQewAwO"
    "LNj1UBONsgwZ1H8BzxCZmxQChketMFHJWaD4sUyQtwVytohw/Ttla4WVq5VFZJ8ZgMwxSK8IMkkUBxnj4WZq8SOe3LqZlOrH"
    "2nyYdEKLr4AErFvnh8ij6tX5oXDmsgtx+CYsnvLkYUe4SHHGHKiXcVAoHah//eM3/1z1J7hr/lS44RFm4kKWjKX0+/OkWZRy"
    "CpjLpTiYQmkddmD9j0nRklSJDdXEOiL5W/MpfLM8Hkr5b3ZlA4tbbPSLBlrimrdcPRIC900tbFTVOl74XfZ4HCWozjLdZyfz"
    "qOYPhFuo5ThOAYzIIvo/quq+AYpa+PiEv/g0bC6m2wQMrraupu0j1peJbdH6IoJv8yC3vRS2a1dbKT8SqYvksCVDFYqvm4qi"
    "t7iz8LGjdkZcJ9cFPu7+VhBEEUzrz4hZFY05JPq8Lu4zK2iPXm19NfRvX67Uv0oDr1HwU2jC3o+fodbkjXGxH9fiOu9P3RpH"
    "V+Ct3jPrxTdIsiGKjrEIfKW4wlzizKMkm3mLywRLbSpi6HV1sekXBulE1uy/XS+E51xErZfbNQpzs6hsgD/HkTzhsinYJ256"
    "KQIoIsPE4NIf4hYXP8ZSwGh/mabxKZYN9vH5IOXMmYQygJK/I80shbzzs/1JZo/Z3I7ewyjVBMIiGLD7W9LOFVJX4F8MD/o5"
    "7u0I7ip6PFHvM8hdM2UEZLjRXDsdZKi20pjQSg9yIuy1SGWfpuIOwPLyCx7a4gSYfC6dAerpVEJELU2WjCvGsl34lpsz43zv"
    "CG0FM9Z/DCpW/AizxOQYLu0+YiqPAEBSiiBSXi/lNgfhdEYtWxzwUqfD6LjjIAxn6PpT4qDDNkQRjUK7HDyRmz1UzD2YzDk4"
    "NqfZWLY2B8bsmERVPe5ckd8v5j05136JNlwVji6pb4qWaJ9V4boUrmlr+mO+W3PdkCSSqrMTpydYrvulyXlViV1ei3oLrRUT"
    "KGVl5yG8Pqbl5E6fgN5wcwLGmJ8bi7lCJeeA9YV+R04wuQFWZqpUdIzR/Ja6HWYuNQmsXLFlqaDUgDFLYw8F5i6TvFSoAdMV"
    "dz0HOK9UAL0qMdirkgB8ZQ+6o+9JS+rIcjJRTPMV8sEagyJiaopJGPHm1wQihabBP3717R/++JHV1RdCB/4XITuS7szU4x0G"
    "6/R714uY2EHwpHbhoumK6sBmTRhOFu8eoWM/hLSUuLiuRcbXP0JVvzC7ZYZVEgXglbgQPVLURtdZ5g2AeighJLKToL3iQDxF"
    "41kQH2g1CuFTVF/lL3T+tZLSiWoRrerRhFjB1n9qcY+pwhiaxaBXhXmVShfhrC/I0drFmMJzVxJKmagwiYhostHLquZ+ahv5"
    "DkYFmEYj68QUbyrOHMiQhQPEm/vvhCiyLrCGB1anPdQDRIb58QK9aX3McZIrFbZ/x6LMU7wVSsv00qv1aJv1VSdBY31BeNTl"
    "2iasaysLRMf+62SDGN+bdfp9QPlxe567h6nbPizPOKcoyK366tutdouKMn4SSJgZeAE8eGRESMapwdkCYzpnJHfqbJmRsgBZ"
    "ZHMQLIDcPXgSwgvSZIRd0UchM6rA15VJcRP0UmSQ+KXI6PCazB/E8ql0Yd6pcx1+1yKkQxcnr45Fhe7Oxzix10A7vPhu8BFu"
    "rIDCq0UGWc56/hk9vHTDLs4RNns6CV9zKeuEDTwtvfR3iHUdXHmy5XMvSNUUwJCcVznk6rLid8oKVJJoU5LVKZyhWJolnzWB"
    "8Y+MSorFJKxeaLQW84GW3mppaqjSgL4yKLi07NbY1wVCVFUk7l+s6TvAnUmhTgF2aO5miBIJgVMhoEFGcO1iGUlaH0cFNMlX"
    "5In9xlCy+5WRJhbLkXw2leAULcDMS9fZEDcqlMlbaIVmLX3EDlJ1xQSTXfdYErog8nBVoOQkpBfLg023bkmTrh2exJljUUjX"
    "+/tDMe8n2/rhQk7fYBT39MfkSjaxDIugucjXlabIgGGl92SXw2IPssPhnwF8Sf4OsF/NTSJxq2qbqmQB3KMj7SYGw8WBFAmG"
    "xzKJXT+T4+DXLwIghKa6NNys0yQ0c5dERVKSvnmqNBXKZLOv5SbH3rxt0uzjT4UiRLFbPGWcdkP1jzetOWmnGj7jeoNlqdBO"
    "aQm9JuEzUZFWESi8riOwmC5x7UKqiH0IpgNMuRJgc8v0+VSJG3BJ8Fv8+rq85AoiaeT3psOoSIpjggQKk+ArYK55ecLK3ELO"
    "Rv9EtmtAM0Rwlxeq/d3TnpwQm7fxJD/XzZ84loi3otSdhIHLhvkOLm7KsH1YctIjqyNr5A61vGT2KOLldPkcccN5/hbO4xe8"
    "JqX4RSgmxVUGLwcQQ41IdIwDtPdbkc4F6xg4RcPBG18q30LO/m85hTstTe2371S500rw4F5KgN7+F2QnhFlETi5CYrDQFnhg"
    "QIixIPmzMsIIi6LPEzq8AAgzht5NwuzejxC8yJSoolh44oyaHfUPJDwWFItTh0CivCgKCiLIxHnCxRYVYZhOP/eCPLXCTkKS"
    "vxiGSRl8EroxJvBS5gCHSEfDbK+b/6fsCK8HH5xNDTb+evAhpfLtuvw34cEqXMaHstS118+V6/EaNAEfhws8Ju1DDSzs65e/"
    "dGRXUO+M3wSKTXFxd4HItAu0+mnqwHn4qv/fMESRr/F28EcReZFYZtMB2ujywPWr8jOxnOctyekmu3WkMKsqlseFJTUWDsqt"
    "hiStFzxp3AfX9WcnIUSD98YhklhQMxSgLelbdT/QMGRhp9FxZC+mtGwWy9AeT/3qSkQYyZ644xRaM/gZvao8eH0KaZCjv7oc"
    "EWHxtx3sQoTbccfDjIs4+E1GLGqHd/SAt1yczihQmkVKcMsnvAIykf886uRFV0h6FR81i4NtsGq8hxsd1ma9zZ7I2IJDwZLA"
    "95K2/BfURLFlKGkLu5D3i+m6B9+jhgoavKfju18S/Cp2Cnf6AqCsKN1djqjbUezDrwp/1mKaTnnEiD57q1QrP3Pc8rwz7JSF"
    "OZmfbE/4/TdX41tYOJrrBUgMU25S62hW2uqYQWXNqLkWloByqzm69TQL6tnG8mqS8Ze23JLz4PXY0M5/oUqlaGikFUJCEupS"
    "RqJU0VMdiYQnadJ6evIvphFb8QHOWptN5RDXOpm5kqwVuk4gB50STzn64dyEo/POW+Igo+dOxynHjTXdWfxS4lpkCLxXtUdu"
    "9u3A2QzrjstVDeZ6kQTKcYj56qXkYUC3Jt12r+uR5tUCKLkpJ/+aoWPdZHv4nGOuzVz6GNq2Jmo6u5ZHBIMbN0MdD5SeLd5L"
    "ePgC4QksHcriZZdw1eUT3naKm80BVsyg8OYAwhkpf/ZBbudD9tlOeEHhzDP8AIAfHvI6HgEH6ToycZVSvRY/oQ2EAitBXazK"
    "VHwlk7hIXBkOBQOgcgBotMbq2kpd4VgxLKyf+wUJrUblgltQVr6uCKp5Vbr8JOhK0OMBHNlMrMCMcA6bPHuuuRbhkucVm6uo"
    "UcWkgC+Fun1SW7awmFl/1GiPfPureM3qWCXalnQD1H6nEm0C275XY1k1DEQcpnsyb9eUw02NH7aSGDuj3cJPiHM4nlK8ZcGJ"
    "K1JDsfiJEcKrCOu+xaSVHXxZZPQoQ4EkJ175FlwATm/rWJ+iTgPtgtaAIYgENiRkFW11rZ9XTkoxDa9zFOckpegOXsPRhysd"
    "V7R4l0Nv0aEXGqsRTqdl01CC9uSJAQtcdO0+wmmChIVrBSzFFE6PHl9YyFfLL13kIFyExqyyg7hKEuEguMLwnNxrpIBrlIOY"
    "iVPe+eQVmW2QGxPOlp3FuWvg7bt08eUl9mX8Hl+7r558czHUzDPEhVN6NZDWmtNabwbiQ8TfC7fEm97UGVBhNHlHlVy9h8hQ"
    "1rTcKCFXtvPSGYFaaXKOpguFRJcEOb0WU91c2GkhWq44S7NrkLSH/uQJJuW/3MaFfim9pE2D4sk7VAj7p4lD278Y7L9QY+Ub"
    "UTeCi3stjFmdlyB10e1HlC+GWLfAeDW3giFgVQxGXid/TnzyUuEZ08cvRQ+PQA00mYFXdvSf8hY850IaVblT/tBznh5tIubd"
    "C4AU6ZqmltoQxiN5f+aujesaTaGTQz4aBS1WqoxhtmhB1UjitVNNVdp2UjMLS/pdqBDXpVix9wL4pluN2Eyl1SlEfN+eD/Nj"
    "QpIchWmhwzqKZuEztvnKCvORB0l80faaDdevfe3cArhBiLPAs24RCqwvWoiLLo0UFXYipymzWdCBzKWuTh1H+SleibDojRxs"
    "1RTTLZNap5+VF9bULUYagS++MAiQRIB2uraYl61sFzFZY5HnsD7tLdMbz6HTr7lMwtw6wOX52KUzVcWKANxP4Ac4f3t7MD3y"
    "MxmyRSVahy9eC74ieeCrEtT7RJplgBNixSPLJKI8wNkp/TZEABVyaedh5yf7RvKJL70j3vE0r4KPnLao4+6nT9IymiJ4wb+7"
    "lGLcvWvLxkkd/UihvwvgDnEv9OGkZsEq6NAIUbe6otNqcFdFBMKlFenKzz0IhSgjU/3Q5hCazgzMKF7O8eNTASGZuln7b5HT"
    "BclLkEpHf37pwIytqdk4L+ONV+gnE/ZVIawPx/P7Iskb/Okj4zK1yWBX7r5PaYqDErzXPYzqZZHhYTFbq4xnV3tPrE0Zlrws"
    "LE8ZDDNs6qcnKyUur0rcvXfIrktpFTWWKQNKSC4SMx3/hHh8ES0mevrdRfj48XefTjr/weUwdNNGINLuehUE3KPuZXsOqpyy"
    "KNEz5ziNTYcFl9g4a90S3mPz9ziTHasVMUjm742NqEOmiHGqmrhxdom/OdHZZW/ICdzNS6u0OPq21PooMPD02b/HuXyOk6vQ"
    "uVwa4pXttWhcLt36a4XLEhzi4OHKsIGAt10vCa4FLWLrJZjZpVK4ek1vW4MngNcaDj1P6dWb7m3vVqzFNCjbkCsD7bXOvHxV"
    "/PvgZym1dIxDXe52sI0mS7SAr2on9rgU6gw2oviT8gNiVU1jgbtwb+WB63qNBXyx14VEUkLy1/kfJ6Sn2nYQ8istjbci8JTr"
    "MRVZp3m9GCuvMOXEwiTQAvD7NVe9SwpnFcPHyjIHYsupqWhjGBcruxDktZtOzq95/bEUB2kscAIzed40zCLPbkDNFchliYf1"
    "9wllvWOozd8nVAmPnOqEOzR+n1T+u/yjSYI8+XRj80qmTnMW3vbDrCQy2BGuP1cEFZlQkd0IIBVWZ/9JR6igTOYlJ8UGfDzf"
    "8Zh3WZ103OOoAgZO94dg73FPLjK4NYsmHi8vLY2dq/JL/xd2jdaD"
)
_engine = {"__name__": "_night_shop_rules"}
exec(compile(_zlib.decompress(_base64.b64decode(_RULES_B64)).decode("utf-8"),
             "<night-shop-blind-rules>", "exec"), _engine)

_HELP = """口袋夜铺 · 你是独自经营旧物铺的店主。
observe / status：看店况、库存、当前客人和 legal_actions（可做动作）。
新局第一步：请你的人类替你掷启动资金（两颗六面骰，十位+个位，11-66），
不得自己掷、编造或挑选；拿到数后 set_start_funds {"amount":数} 登记才能营业。
行动格式：动作名 + JSON对象。按刚才的 legal_actions 填参数，例如：
  work_shift {"focus":"tidy"}
  run_shifts {"focus":"scavenge","count":6,"stop_on":"new"}
  work_shift {"focus":"repair","item_id":"从库存选"}
  work_shift {"focus":"sell","item_id":"从库存选","asking_price":5}
遇到 pending_event，先 choose_event，event_id 和 choice 从观察中选。
close_for_now：歇业；reopen_shop：接着开店。随时退出，动作已经自动保存。
collection / encounters / customers：只查已经发现的图鉴、见闻、顾客簿。
history 0：从头查公开经营记录，每次最多100条；history 100 继续往后查。
new_game {"seed":17}：仅在没有存档时创建指定种子的新局；绝不覆盖旧档。
未开局时 observe 会自动创建一局。没有必须完成的回合数，店主自己决定目标。
stop_on 接受 new/rare/event 字符串或数组；省略默认三项全选，[]关闭这三类
停点，遇到必须选择的事件仍会停。公开目标 goal、心情 mood、public_line 都可省略。
请通过指令探索，不要解码引擎或查看存档里的隐藏资料。"""


def cmd(line="help"):
    """执行一条指令，返回可直接 print 的文字；每个动作完成后存档。"""
    if not isinstance(line, str):
        return _json.dumps({"result": "rejected", "message": "指令须为字符串"}, ensure_ascii=False)
    action, _, raw = (line.strip() or "help").partition(" ")
    if action == "help":
        return _HELP
    try:
        if action == "history":
            after = int(raw or "0")
            if after < 0:
                raise ValueError("历史游标须为非负整数")
            params = {}
        else:
            params = _json.loads(raw) if raw.strip() else {}
            if not isinstance(params, dict):
                raise ValueError("动作参数须为JSON对象")
        allowed = {"observe", "status", "collection", "encounters", "customers", "history", "new_game",
                   "set_start_funds", "work_shift", "run_shifts", "choose_event", "unlock_location", "close_for_now", "reopen_shop"}
        if action not in allowed:
            raise ValueError("未知指令，请先 cmd('help')")
        with _closing(_sqlite3.connect(str(SAVE_PATH))) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("CREATE TABLE IF NOT EXISTS shop (id INTEGER PRIMARY KEY CHECK(id=1), version TEXT NOT NULL, state TEXT NOT NULL)")
            row = conn.execute("SELECT version,state FROM shop WHERE id=1").fetchone()
            if row and row[0] != VERSION:
                raise ValueError("存档版本与游戏不一致，请使用对应版本的单文件；旧档保持不变")
            if row and action == "new_game":
                raise ValueError("已有存档，new_game不会覆盖；请继续observe，或在另一目录建立新铺子")
            if row:
                state = _json.loads(row[1])
            else:
                seed = params.get("seed", _secrets.randbits(32)) if action == "new_game" else _secrets.randbits(32)
                if type(seed) is not int:
                    raise ValueError("seed须为整数")
                state = _engine["new_game"](["seat_a"], seed)
            if action in {"set_start_funds", "work_shift", "run_shifts", "choose_event", "unlock_location", "close_for_now", "reopen_shop"}:
                state = _engine["apply"](state, "seat_a", action, params)
            view = _engine["observe"](state, "seat_a")
            public = view["public_state"]
            if action == "history":
                result = {"result": "ok", "total": public["journal_total"],
                          "entries": _engine["history_since"](state, after)}
            elif action in ("collection", "encounters"):
                result = {"result": "ok", action: public[action]}
            elif action == "customers":
                result = {"result": "ok", "summary": public["customer_collection"], "entries": public["customer_book"]}
            else:
                result = {"result": "ok", "version": VERSION, **view}
            conn.execute("INSERT INTO shop VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state",
                         (VERSION, _json.dumps(state, ensure_ascii=False)))
        return _json.dumps(result, ensure_ascii=False, indent=2)
    except (ValueError, _engine["IllegalAction"], _sqlite3.Error, OSError) as error:
        return _json.dumps({"result": "rejected", "message": str(error)}, ensure_ascii=False)


_LICENSE = """# PolyForm Noncommercial License 1.0.0

<https://polyformproject.org/licenses/noncommercial/1.0.0>

## Acceptance

In order to get any license under these terms, you must agree to them as both strict obligations and conditions to all your licenses.
## Copyright License

The licensor grants you a copyright license for the software to do everything you might do with the software that would otherwise infringe the licensor's copyright in it for any permitted purpose.  However, you may only distribute the software according to [Distribution License](#distribution-license) and make changes or new works based on the software according to [Changes and New Works License](#changes-and-new-works-license).
## Distribution License

The licensor grants you an additional copyright license to distribute copies of the software.  Your license to distribute covers distributing the software with changes and new works permitted by [Changes and New Works License](#changes-and-new-works-license).
## Notices

You must ensure that anyone who gets a copy of any part of the software from you also gets a copy of these terms or the URL for them above, as well as copies of any plain-text lines beginning with `Required Notice:` that the licensor provided with the software.  For example:

> Required Notice: Copyright Yoyodyne, Inc. (http://example.com)
## Changes and New Works License

The licensor grants you an additional copyright license to make changes and new works based on the software for any permitted purpose.

## Patent License

The licensor grants you a patent license for the software that covers patent claims the licensor can license, or becomes able to license, that you would infringe by using the software.

## Noncommercial Purposes

Any noncommercial purpose is a permitted purpose.

## Personal Uses

Personal use for research, experiment, and testing for the benefit of public knowledge, personal study, private entertainment, hobby projects, amateur pursuits, or religious observance, without any anticipated commercial application, is use for a permitted purpose.

## Noncommercial Organizations

Use by any charitable organization, educational institution, public research organization, public safety or health organization, environmental protection organization, or government institution is use for a permitted purpose regardless of the source of funding or obligations resulting from the funding.

## Fair Use

You may have "fair use" rights for the software under the law. These terms do not limit them.

## No Other Rights

These terms do not allow you to sublicense or transfer any of your licenses to anyone else, or prevent the licensor from granting licenses to anyone else.  These terms do not imply any other licenses.

## Patent Defense

If you make any written claim that the software infringes or contributes to infringement of any patent, your patent license for the software granted under these terms ends immediately. If your company makes such a claim, your patent license ends immediately for work on behalf of your company.

## Violations

The first time you are notified in writing that you have violated any of these terms, or done anything with the software not covered by your licenses, your licenses can nonetheless continue if you come into full compliance with these terms, and take practical steps to correct past violations, within 32 days of receiving notice.  Otherwise, all your licenses end immediately.

## No Liability

***As far as the law allows, the software comes as is, without any warranty or condition, and the licensor will not be liable to you for any damages arising out of these terms or the use or nature of the software, under any kind of legal claim.***

## Definitions

The **licensor** is the individual or entity offering these terms, and the **software** is the software the licensor makes available under these terms.

**You** refers to the individual or entity agreeing to these terms.

**Your company** is any legal entity, sole proprietorship, or other kind of organization that you work for, plus all organizations that have control over, are under the control of, or are under common control with that organization.  **Control** means ownership of substantially all the assets of an entity, or the power to direct its management and policies by vote, contract, or otherwise.  Control can be direct or indirect.

**Your licenses** are all the licenses granted to you for the software under these terms.

**Use** means anything you do with the software requiring one of your licenses.

Required Notice: Copyright See-Sol-Lab and the AI-Gameboy contributors (https://github.com/See-Sol-Lab/AI-Gameboy)"""

if __name__ == "__main__":
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
    print(cmd(" ".join(_sys.argv[1:]) or "help"))
