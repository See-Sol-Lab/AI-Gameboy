"""口袋夜铺 · 单文件盲玩版 0.3.0

给 AI 玩家：你需要有 Python 代码执行能力；Python 3.11+，无需第三方依赖。
下载这个文件后即可玩，不需要整个仓库、MCP、网络或模型 API Key。

    import pocket_night_shop as shop
    print(shop.cmd("help"))
    print(shop.cmd("observe"))
    # 新局先告诉人类要掷启动资金,等人类亲口发令后再掷(两颗六面骰,11-66):
    print(shop.cmd('roll_start_funds {"human_words":"人类发令的原话"}'))
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
    "eNq1vWlTXFeWLvxdv4LLjTcKqrJclmS73KrSG+Gu645S3KpyR5dvR79BEASClESbqRks+yqIACHmUWIWIAkEAk0MEmJKhv9y"
    "i3My81P/hfs8a+2zzz4nTyJc7tfhsJPMc/a49hqftXZpaenfOge9see55SFvZSE/cfi3zqHvP/3k6n8ePf7tlezaiD+zlh14"
    "+bfOri+/ODse8RcG8nPj/uKqt7F8tj96djiZn93NT51mD0+zmbHc+OrfOu9fuvTVjRJ/dtOb3Dzb78yOvvQ2dv/zaN4f6OTb"
    "j8f8hcNsZsJ/spCd3EYH3ttxr/e9t/EYr3rbU9mVw+zrTW/slT+66k/uej1vvKPO3Np9b/Op92g4v3ToHY75M6ve6Qy78gcO"
    "8n1juaVhb3DdW1j3p7e8sYfZ0S2M9+xw6Cyziw+5Dw/8w/HcyUF2athbeXB2uJI7nUWX2bfT/mL3fx4Nn+2P+POnOlB/cPUs"
    "s+f3T3t9h97kRm5mzJvoYk+lpaWXLtU1NDe1tJXcqW69U19389KtlqaGkpqm5h9LzA+16XQz/7506a9/vPFP3/615HpJRWk+"
    "88CfHStNlZT6e9tY49LKS//0zR9uyG+t6fp6/tKSbq6ua+Gn1prq79ONt9P8XNPeUt0mn9qbb7dU18rHtrraH/WVmh9r6uWr"
    "2rrWhrrWVjT852+++R/aq7/w1Dvp4a9n+xP++3V+yg4e5LZfy6fuF7nDLvm0sOd3Dcmn6Xd+t/zqncz4D8bY3Ff/VvXXP37z"
    "z1V/+vpfv/4T2v1cvvrD//rrt9/8+et/qfrXG3+9IbP8Ur7/x6++/cMf8dcXly7d+PbrP8tALpXgn7LSu9VtNXek7a4FbJQ3"
    "P5+9f5B9/MDv7MwtyeDwv+z8tNfbc3ay5vVnsoudoB5vbNV/t+T1znkbw3g63zXhvx3AduCFK6mSL1LSOoa+9ij/qD/fNwIC"
    "yH3YAjH4M7spf3PMW3kJUjo7emz7xE77T8fP9l+dHR56K48xHHbT35t/9JTtlqfMgL9LyyrnNlbyk3P5mXX2nnmQn1jIP1r1"
    "hudkKhvdfmcGLecXn+VOH+bnhrOTT/FofrIL3XsnG/wX5Nj91o7482DEeDe78NR/+xwdYLnROqlwdhOvp3Kdw/jkz5/wSC2/"
    "xkDxEJ7Orm2dHS+ASPG0t7DlTx9ERgzKabnFceXn12XeD/3H01zimTVvfsfbO5FNPjz1Vna8k37MPeWN7OAoZKfmsNj+3hL+"
    "xePZx/fzL+bsiD8LRpxbWvVWj/2FTm98FEuGFTRtjY+mtH0sc24DQ8QJ78R64CH/zZI/tOoPbnMY+y+9wxeREd+sa6mVQR0d"
    "klMM9GVPe3K9nXx44dBf3srvP1UCHszurHE+i0vS20Y3uvIXFr3hGRxrb+w1t/D5lo75cqrky2DMIAdtMve8B4Pny7Zlb3Ib"
    "Z5xL2bPrbTzBisus3mFtyPMeP8idTub6X3mL4/6zvsiw69NtbWk5rCTM/i32PjLIN06e5LqGz06X5LAHK0XuBHa2MKCrhh31"
    "xka8lRF/974/OsABjIMJztgVv2qp+nDfO3p2drqBhzl0vBl7x/+wcXbY680/AUfmbioNYVQYA8hGqArMfT8y/LZ0dU17sw5x"
    "IJvpzT2/nz3kWcxNLOaGd/3FTfltcdM7nMpOBgfxcA2Ne29nQe589PhF9nUSkUhbIJX88bistrSiT/MEPXrKnZs9AZc/2x/i"
    "po+9xfnKnfZxTv0zeDIy1prqhnRLtSw1lnBoBKud6x72jklQ2fl9bKb8NvDy7Hgu170LEvKntry1oWymP+gF/3ZbyviHYKD5"
    "qQXQrl1bNi3EkH3zBs9j2bWbFGn6+A3Gh6ezC0Pe+EM86j98kOvsiZKyYeTgVlhVEGP+6XtOaWssP9EtPzzsM2wpPwfSesi+"
    "ura8rVnpIYN/sy/AS7YKmRsayPUPc5yjT0lRmRG3k9TZca8RrV0z3so2hDXZ3fgwuuIR2ej2usaE8oai3OJOk8gOsEvO7qQ/"
    "d7qQ29vkmEemsNjZxxv5JyIX8D/sobdyYCgBa7PyKjfwjru6um6X1rI2fV7ZRXhcySZn1nFcc32vsBBYVKylN/ZCmPwrvINJ"
    "KG2Br+Gn6GDT6dqbTT8IrwCLnezn6onqkJ/oys4/kh/mH4n8IDO7BlrNveiiRjC3A17oD0xAi7BL+1s71Ml+MGtSwREPawpt"
    "5PvC05p998iMHBz1Oc75WzCh3OAxex/NZB916xiizKG6Qc9W51Q+w13OLU9nx0ayXXKqsr3Y9U10BRYANs+9x3LsbZ8dbuQ+"
    "7BWKCbBYbApUIV1Lf2BE9RsuarZnDa9xwSAs+k/zMzsYO7jO2UEPCITHf3lLD9bZ/kJu9TQyzIb21roas6TeFnl1bvC+PzPk"
    "nQwJS3xN+tWFhRjNdy77UzuQnqnsy0Nwax7l+8/xBiZwlhkF6VCxOnoGNlTIhLNb0CD7Qp6gT3MNjw5xmM4Onhpq3YVQ2k55"
    "3SDXFVLg/CMsLk7y2eGoN97vrY5FZnC7vun7tB65E2x5fmI3+25AxZ0/MOStzshvw33e1nT2+bo/AnVoBm2rWFUOnFt7gTXy"
    "Z5968ycJa3+0SIEnLXDc2oMShL80nF9czo0f+/3jpGAsuSgb2aMJv2fZG5v1hkX02qbtsBub2tI3m5q+k5O19CH7rMvrfMTx"
    "Q4kGsey88BfeyLncHfROSJTZ00wKCi/1OaEZ/ODPvCxkE2cHL3IPBi2bkJ2aO86/mEYv5G2jWxQVhzNn+xl/dlQOxYiR2PtD"
    "QiSd2TeT/uQmHo6ytva2tqbGf68WiQdB6meWVNXJHh77A8/Dw3A8bsiFkv/J43z3MfcyM0rBMT7sHeycZfh0bum5vzACweQP"
    "9RquFBUiaAgGCU+lYSA9uzh62qj2aTZhBjIpQ0KHnnTaB/birUyDkMBL/al3Oqio5KtrvHunWnVmNjF24G9NkpbBRMDu3u3L"
    "DHsO0BsUf8Putsb8Rxv+h73s/LilbctAjFKyMez1rNM2UTZi2xNpIlqQcmzp0Oh3qn+YHjY++McbRoXBcCtVga76nzf+Iur8"
    "PenOKNHXsMYzuzjuHC3VVHzhHT/CmTL2A7RAfJWfg94rz4iaxbdE9SnVsQdazDXquFveaa/YFqoaSA+r3r6shxHBkedE2rHb"
    "zQzkTdCiiBQ+B0myNCyDMXz7mvLtqVN+KRyS3/SsgRD5jWVGHPbT92cH40GTesg5HjlJfNgeIPa08yI7vyEjskQqg18Dkamx"
    "ZHbcnX7HpUuBBeOaKDVN7S11qtflPkB2voZuQhlHXrfh7Uk3fvd7f+CE4jSzm+s+5hpDO6cINcIzMJfvl9pzmZn2BwdVcPqD"
    "sypsoX2DKowitbruT66SO530Q89VIqtwVjHcbbPNlSDCTyP63B0dd76z8+yIQgdmpv9sKdfZ5e33m3GfHWyZcZ/OYujQ+qGp"
    "qw4Bc1f3NiIrLI2vHuRnNmAVe5A+Pf1QsMBIzvahb4zk53fzj7ZFBVECfz18lsmcHU9pK7mdD3Y2lnbMBmMOX4bSKF1zp7qx"
    "rkbWfnkapx9M3X9HpRRsIDve6+2tmmlACcO/udM5sDKRdwPatVpT3tiK3/nKGhCxfQAjyvZve5uP/McPUv7zTv8pZNJp7niD"
    "5trITn7xCWg+1znunXYH4w6IxtI61/6qHfjdutqmuyruM94+lJkV7vXRE+4sFv9FH8gjTjd5+DnG+8GeVWgL0fCwFZIOVp66"
    "ERZfltNyRErdfTJvb+WVN27XODyz4dk3hwyj/odQm2prr003tgkXBAlAvZnt8lePSDZvX+CcSgsw4V50gU68/Q1VUbCDOG7w"
    "p2iToJlsZi2beasHO5lyxK2ku+StTqP1fN9DmCYpo1KOwGp8B+YN+Zx9eWpJxR7qkEMY7oFp/Dak++q6+iYhe79/x1vozS4c"
    "Qavnyj/vguw2rg9Khc2MLP6o8gW4kagg7K1yVD1GSy8cPM/tw30e1/1uf3qO/qOjWRFHEMsnnf6DU/hIYF4o4Rk7e281N0C3"
    "wllmlvL0/kG4NwFLMntDOrocbomdC5iAKnC5tS5KHbS7tYPxFpzi7uPcZheWB3wCGjOsguyDXWufJbKh3OFrmtKY79iKt99F"
    "saxOAFCuCjsIWG9s8ywDk/0DDryIxl3I2wSeZM+F4cwRCoNfqkU0HEh/H+J+qT//otefewz+xf3pGvYezrrHYlRZHJ114BPH"
    "U/S/iSljtyiRLWVxfuERkrliXH53D1mRnI5Dr683u7QB0zj7dhInKL88y4mr+jN54m0c55cfZDdmwv0JeGxIfs6Jv6JC+as/"
    "/+ONr//yrRUadLVgeyD56UEZms8ODPuZHdUJoRfAuIYCD5fDAIQD/U3QWV5uZ1/NkJPC8QR9THY7nBa8LDM0EBbHhMd2ZufH"
    "UmeZQSxd7nRevVD0vB4eQrnyNye9g/dkHPM7/ruBfGbWaSf/eNJ73gUd1RvuIZ/p7IJursoGPb0j07CZqbktvdFnUoadPr4v"
    "duMAuocXyHv43mmTRsJJrxWM2Ftvbw9nXNWvlCpcub2nWAu1aPMLfTqN/OwHpx1p/pCMEiT29gQKrpr1GAlYO97Af1PGfZKB"
    "OYMleooDgV10GvG2h/xX40rP2eHX/siydPUKTurs8QatCJ6E+YfZxecQFthbTNAKC7LR1WO4q8/2H7uL9nwUoyLHGD+AKmc2"
    "8Wgx5T9d8Ma2TGfwymw/9EcfcZuxg6t9KnHU0+NuZWcX/B0wB2RgK+pjTMGOQqPYZp47DFJsTY6QdudD1dK1EdDbpX/56l9u"
    "fHvja9EBoaA0NDQ1QpUpI2kqq//sS1BnOT3Eje7PWw/BPqhWfyY/65Ex/5S2VLek9bHVPpimVGk/Na1UN9bUUTTwV3EdrbAP"
    "+KT44510XUt9U1OD/Apvw9n+tPFYlXeovirD/f8SFFYztlBhDb+wCmv4VaiGBt8ZldVojuGTEbUv/DrUbe2ypEL9NPxOmw01"
    "XFmZmELqtuDqns4gjDYcbzfQu90WXIU06M3RksMHrebrtNpx6U/f/OGrb2988xfHKKivbuRz90obMY1A+4W7dG9PQgPp1pqW"
    "uua2OqGMUlfTANuFR5Feo9NZIwQPjTWGcbSSCC5HKYeDqW+q+a7K/Pypxh5qMFJozq3yTeyF5qYmrk1FGAAwjnXrrQ7dkYHr"
    "JGJwhs5W2b7KjsDYaKs2kwpn7h0+9Y661duYOHkjZFTrhR4AOQ4vLw/1zFTu9CA6+SuxuRTO/8uC+X+W8E7hEgS+t9C76bpj"
    "XA+BkJadcy36jkyY3gN4MTMT3uFEwoQprvtfUdMXC19lNrbdO7ofaAd2tlfP3+rLVwrm+mXRvY5vceDnd+1vx6WnpM5ZdlxC"
    "nOkv37rUna6+FZkyJC7Mc+HD8LPsKgX90CY/PYe8GKWUPFq0Ag+uJ+hG0HBUVNsXOftgXVvSt9obayPd5E6f4n0qQGLiuN1Q"
    "zxMZ7A/MUhKDnuaf0IeWmRUxsCJaFDUsu8J1jVywKx0OH6tq1oV1uhTRjyAWvHpuf1D7VX3Q+BaUSjxgJC+dyJspo1SM9eM8"
    "66M0kdaC/hFcbLen5XIwiObqlpp0fYxzPGNcYbgn9/wgsrDQy3bWRGZv66pCAaWo3qfX3Dtezg7uWqUzBbtBF8Efh+N8PLdz"
    "4KhtDrnU3GmqqxFKuldaXVOTbtblqK++KcOC7jh7xS4lQsEg4pQ6ctV0c49qR+G5c7uqTdfU1xk2adv3Xg74Q4/C2QZMraPD"
    "7hMOQLq2SnmzQ4JwGR+PKcv0hp9HaGO/B9aqqgs0KlWii4vb2+ry32bsWykIfCg8FP7HGW9iJHGNCtapqTndGJ1FbnA7XCVY"
    "BzBBvJ49uNawThdfIemoTULMkdahrWCsCJlnM3PYAqUCWEAzl22fkaX7eCc40N/HN2K8n97AwWNveyCV23hJ3/bUHCO28GSq"
    "VyuyN/Df/PcS/tY/ryQHrAJtm8wxrdPJ9XznJJn8RBewCfwAEoXzlKGVLq9/EdEh+uugATIa2XV2tOV1HtHyWFrPbS/xGwkK"
    "ZddmvU1qYuiLLs3MLvdw4/HZwYC69AAcgN2TH9ihHFngsfS3n0EtF3/43NnhvDFldk5gvLKdP3/zL19XxePikO03xSo8pi8A"
    "XkewKWHV6/7ye3X+WEdcqN5Q5Md8pkeHaMIGhsV02IFP0T8wdnWpdcBj4Ghbw10mYIgo7thDfK+eSXWq+rPr9CLtDWkMAf5+"
    "b+EQo4t4VNsbbrZARFWrR/WJ/+6UMafeHm9kTxkCvow6JApm4YaO/EcPebxhgXRmQHHYVH8GEu4xyWFk0H9rogvsKv9q3YZF"
    "MHK4U0w0V55jlBGBfvX1H+zm7tPY4aSGl+JTaLtT13BTZZINmTPMvwS+r74za7qfuwOcNRwPz9fVkwceTQqBht/PEAkseEYS"
    "xqatx5uxUrJw+OyDSZjAtngL0Tm5+/RRdmYe8QRjU75ZMrFCLO7UO4i6aJhMJLDxRlHBQ0RNWkEU6XjnJ8yFkf2tEzBbcQsM"
    "IMylPny2lZkIxn+8A0eZdUqRrIKQN7tFE2Ov6GhEGGW8H1tB4bS5w9Mogiu3uYnJRmNn0HXvBHG+ebrrzvYpg/3xV9mJvfzq"
    "2yAiVfxMuNTECIgE9GjxIaov8Ibcw22wzMCwDcKG5HOwpXUWImPIhIRkMMj8jFio4gZTlz54jTfSjxFFo9VQbr4zuAAjG8dW"
    "vTEeBcam3kya8YfO0PN3AQEweMlGh7ALJGuocnPH2pAZfH5iKz9xkrgFcIyYPmemMAWCPMDCEReEVSdYmtzmSQzw0tZmjsHz"
    "XW92B2Fjb++FyisoTvjy4+woPMjQtLrX9CzTTzkxQgv4+RZGCAQY458bA/lFAyAwHcJhTQ9ucBJAw3Q/9vdKlGQFSAIf8fLV"
    "Y4T9GS8UNIl6x2LRqtbmamChbCxeY2fCU/vhakccW7bAerIc+9AoSdGp5DvHJF524G3fV1pSHAeP88hWcBYQ1157BBabHVg2"
    "DEm6Uj4EZRL0o+SkfncTFXreiccQ34+GZtPVrYhENN5uq25OB/FZOBpGBr3NfeFwe97WYdRVlXQOLB1BhYV0UiSRgZ6MjQGL"
    "Fqz+0QFCtBFmemQ4KTrURfdWngJnx53AgYABsbGrzqjc3iJgCzHIRmNtfbq1ra7mOz1f8/QHLSz57+klyXaDm21Fnbvh4KGS"
    "KsotAu7qns/Oz3Lp1dHfPZ8b3IzbbDwoh2vZ9ff0aMskuMTwxYHhLSwF8cJnXAFgFmcIxMDGwImEdsGqEwASNMEaqtWNyZ08"
    "HmO4d4b8CKFW+K2KnWR3Ek4gfz/7csZ/So7q78xQ7gqOx385ByhFwItezoC9useZ8A0BXqgE5rle+iCO/8dnp4ukpcNJdSx5"
    "90fgJYwSUnWLEWxW14Sb318WkAc2feyZE1P62IkmYEPwKzzC0hxHL83REbkyzQ4Q+gafGhoJ5vN8irweItHyVnmBLLXzMbE0"
    "k7v5+V5gabKvVxkfPh5TZQOP4bRFJlPX+F1zda1BAuHgkbmuTfhboofjTyWqpBOB/bhT932cqhBd8pbXNf7gHbzDAaP+c3IA"
    "FQaeOcUU0No6XLb60xtGAkaWY+KabFUICySB+XD0k7v+yIaa3SQswGaHerBdeKYAglNfXSM7xH2XkI6/eKKaE2Mk+y8uxKvs"
    "SSeTXaGNiziLt/0EIAiYa5BbVnqj0UB0BE9QvsBdJDNCJNOfem7lnuIy1IjR4aj2Qe1SA5V2LtXNLTqwAEr8mGrA9n3uzvxO"
    "7vncR7SPiBa4ADTitsQp2BajMB/2MBGophTpjx+YKfiPZ6BcuHqtEiZXceBEgHmDuv7G7/9uCdaBkX42yuccl9uNdbdMBBhK"
    "mMKzQpQNogYra4gwOaGBjzMvRqQAfpHgkcLtPCXZngEbHSr1x5b8pw/Aga300J85kWd9ihKgxT3wEkYNJXwPLX2EMv3uhSJY"
    "0Mamu3Cr3NTTP/8KrAvHLQsEy/y0CSnN7WbHu6O6ueuotLNxUXNUBfpPCbvqE13w1QykNJdnsTM48hOgl+ewde0pQe8akRFg"
    "yKvs0BsqUvCYCI6VDFnwLxihCsWoMGlqsNIc8hYcg+ie09ymYPWOZyAYoifEnYK4y2QClz+1fBhBESCFu/rgHsltjeY2FxUw"
    "wmjF8go4XHA8HvVTvw3QNGRdw334kjrt/U0aORjLcBfN984ebwto1FdeD88JV1cGGKWtupYWE9/rfARcIVh1FuGJhSN5fMhQ"
    "VShNEnfiijsRvIKQSW5nRyN3RD7idI1segHaEcrhLg5gxOxDryJHiD2Q7lU/IRhyYER3Ayao0U8gPN+/iunnMPVu/gjkeZMB"
    "7irGSGXBw77s5gZQLRiKE+ePTSbkW9yWy5awJre54qSBIdJMAJFUwCjtn57l0GwCxNQfOnJtPx0F9EX/0VtKBnieOntodmFb"
    "xt8AnKMBGqChdJj+/LuosG9JV9fCPSmTUjw0DLZ9Wo15yKKDdyHOMPm4hBLzy5j6LlB2jrXvGXRymLT517Mwjqz5MQ3mQJFv"
    "ReTmGFgNwn166NUtz1kqNnFrW3mr/wwi8gmhcXKOEtDVLdV1GGB1W8iVDV5CIJHi2lw37DhkzMnnJ2QAiH0HTcEBSDULEnBB"
    "odMAZhwFmwSDW1hzyNHsa7IT5IIgWRmKhpy9zqcUpXtDcFkI7iPKCYAPqQ1AtjAnXNg1D5CCbJNpzmVl4QGCgcsgQDch9gz5"
    "7cPGfkXSN/E3Ad4qW3asq1fsWySIvq+aJTHdD4+8yRXD0fq3mEoys6sIiRh4vFHZ2ewzEGq+s5eB69mnmg2h0sKJqsdm0nSz"
    "Nd3yfXVbU8uPZjpX7HTGqfHml2fwpkl8GH+IkHl2LeMiEcg3/KVeV8cEP8BrdiSu0CEf33wgUZI+bzSj20LpOX5sWrTzutVU"
    "X5uubahW8OvgrJqdudMuDEBAfzNmPqG+mcwXIlwO+HO8SVuWTpkeAhQ3J6FLM9FHUFTBMTrcBzeEQz48RsEQspkp2qEBr6bm"
    "/eDU6x0hD8wYfRN9wHyL0hvQYLfrjewB6lHY7Ap0df8dkez4r380FkVnxWjOKJ2RXQKfwpvGO7c5CYQwG0KIGOfncD7YouV+"
    "IqBcg0xeA/Iq+xaejB5umr45tUVFAF92yqCgrPVHrTHw6jQCQi1NenJUP1ZPhrd5AMlgItoje1H1+eMCiEQGOkfOmHIlBREv"
    "GW4cmGUjexSjo0N2X9AZ1TKQBgDifYfGKgUkbWPLyibGIbpOgTzyBl/GcODIvAqYAPj6CbatKz/XS/8rpv9hL/fk8KP6wJWI"
    "4Ol7CEkjXgqil+F3pTa1KFjcB49DjyMaJgdzhKkG1yj9lX1B5ACxM9VzdrDkja4Tc6HOAjgdJ0/IHJdnInNh/AcBMjVpFrY8"
    "qECngt4J8FSwjnnalB8kqwaRUxPmNtzfyB4Rsmz4gMgLqF6wd0I+wBOz9sglMh0EGVrvHNyNjLhoFokAnADVUQ6QoG22NDW1"
    "NTe1BXb420mCgzOnVGKxjMj+me91QFzJkjOqpc33WnsfvnsODjYZRNf0lv9M0sa2JkMXnjpSXZYmnj8DBGLWzOCsP82Yof9k"
    "EeALmGIASpG9wb89u4olipll1QD11dQrtYBfbTNFESr3hy2BEK1BKYkefBvIjyg3YRaSaI60wQbXyZmWhg0MS1sGDmSB+RBW"
    "83zqP+yNbIw8p5vpj41DVbMpa1De1Ftv0jhGtvNzL8UvgxTK5zHwM4JZbc10sWrOzCvKH+RBHYv2pq6oR++jxyd5ZqF18+g9"
    "uiEDGFmycGnaOxOLoK+Ifyni1Rh4pRFpOsneTtId8PwJTYLjCXgBiH37gGjfoIJvJdA6VGCsNbXdAeUAGqA6W9cmnEJeD3Ut"
    "Uvb8iYZGs2+Oor6mYEIRnSBU2fAGmKHkIGpkzvjaBx4ij8ymmJUy+PBkN8KhpVMzE5wTsRrV+KTEmVqGDGLrZHEZb7sntjW1"
    "iPgH7lcrbLx3+4zgbI/LCLpgWkWRd8FcQj3tSniCJnZV14Kpp4qSv7uuXjF8Bk7YsdeWnuR7RuxMtGNv/AGkhE3N0lRMWEuc"
    "4eMxdWyQU+v45vdhUUWmBEBv052mlsbAYYPNheIkSWsaX/GmEQ15G1XaCicUbo0+T7m4sKikRmMSUR8kph1bh9ODwRgnIJKL"
    "Gls38ZIbLyOAFxkNozWiS2I2ihaMMoPvfqy+CYCKqAHwmElGyhTUpNwxzyypbMNaoVZ6BhMp0NeuWE3AX3/lL3cx7gkWN4IP"
    "A+TQfQf+WiA7oaaByFwTVLtiTGVjRhU06nsfuqjyCRwVoEJaL6IJCNQl4lZuwDBa6m7eVL4LjxPX8WCRvuxlOWn7i8bjFNoD"
    "ieflt44OwF3ITKgW7j94ygAowzawT/aCeUwjd2MRhyUUnWvPFV5Hr9fJKd38x48g/SRydIhQEWwBRV8wAWc5atbUNjW1fNfI"
    "yLw6aqbeiTnwWnOK6JYe3Yzqmc4cQp3syuXQ3bQuLHmISMguGFyTqgswrXLqXRjsyk92upuhPWl2MQdxZCDB0MZCx0Dg5qBe"
    "M9AXj9fdarp9q1o2Az9SGRI1NC/MizJLRX/oa0o4H1bos/lX60awvKVfBhBQ+lWmYeedBFuBh2AmQ/PqWQ+8MyfMrcEUPmxY"
    "R1OAvWUoieJT9ZdE0V8Lw7mhua6+3sDgn0wRfAOBMIGUt9fKwXPHm/g+ajt/RGRCY0SXYKT0zoA8RLnSJEXJzJ0Hwitkx9qr"
    "5mtZI5pkDUnSzRQtqqUiSUCebI7R9RfUMAY/5E5OEvxOGFZL4Jr1504ouw/eaUIXnQ+Dr2HgRs204kf+qhsUAwdBSHj+EEgC"
    "Ahz2u+mvlE1jU4drASMDKP7wTcR3I32aTHZVurenzCkC8YAM92X3IC3noCrNSBLISzDIgkRKQEhq2+vbGzQrtTc/uYLG4PbR"
    "xEZvfNBbfBZV15IPUOiKkvR3//0qYRZb22hTQ+Chz4ZpYqObEUtaOubuQINBysrCM5vSyQzeDTrXNQeBY+p9E1fSauqrf6wB"
    "lKyxVmGCJta38FojNPm5XW+0N6qlBdjW+ESuWp6MtwgX0+0IAqlwtDDl9ukkyDjYneVR5p0jqj1kvBvan4kGCO0hsqAJjaIC"
    "3+ewAGJQqzo2l5twnf/vdFonYki9f1GBIPnFRxCWuc73UUlZdC5hJnbney8zQR1gbVPk5Yi6i5g5o+kKGjgVP8cCEmEVumQY"
    "9M4O3rcHD+8oZhnlQTT+7S3OZJE3tHhKJ4d4ksLkNWMTYEwtsNdMVvR773AQtinOosk/GInFa5wZheztalgvASEepKMTfwBM"
    "PT3jSLVktuWHrtBpG8s+F68Te1Iy8ycP1JGA0eA1zZ5ggG00EDY2D98Rmm1paDE4NaqbIU2FmYZTKHywIGSG6G1XAU7EmUsB"
    "O7jqKM/9TFlByKKTkVWAMgnN1cDHykIYFaTXWXJYQ6XG5GggurHCqglQvwD3H+mG8qwvS5buoslNRb423FOxNGWqnE0t1aaA"
    "iDopoRUyC1E1tFfrgeVpjYHkLbLsDS8iHquAdnLY0WEo7UyF7d2jY0JSUEP9md4/+HCR16v8QDqmHBI3v1YcUL86cht4uoXQ"
    "sJ+A1fv7BdYNGVtbNcKdbaELV0mVGSJiM4JgsxudUc728XPEt0SinR3tK8IIrSm3yS87u6StuyyOfjXpW+3QbGYRy0NuMAI+"
    "tW6NUPKKIKtckxeiE2tHMRhlDUxqv7+pTnLNGkPqGlBfUavgXOKzAhavMa2ZuV87sC85P8kgos87qFdSKslxDIIwhBaEPA3P"
    "ltwUWjSaRzj2Dmap5ZnZI9QLmIIRFLPZmhqbIXgE8JYd+EAv+0K/FnOAcw/yICpSz52J1UE1ycZ7ch+rouFpa2Br6xpAQIKY"
    "9XycgrlFdko6FyVoyLBoEB9Yx9NRoBvUp0MC0oIthZCHW3UtrW3f1dU36nmhL4s1XbpeS4zsYfbZdNQILUp1oU46/VYVAwq1"
    "4T7kJPvDA2qKkcPtWUl0dAiNMWIjPJs2wbmu10Y53X9JVFuQinx2+I72dNdjTalSvShWwqC1LdTLSpnw83pO8j3EZofmNT6C"
    "TKeokm2TQ+JK3eehyfP2OUEC6tV5O0M5I0k/9ID0rLP4DQGar6USyCM4b4M5jo1nx3si7p0BbjA0Vo236YhYBUHNkRcZ7JfE"
    "f8TVO/+kqOOqvbEBiXfp2uo2zDnIV4OPHz5vA4+cZtGo3uEoI3TnGtnAz91sfOqXkgsPyAb1zp0dTIB5VXDPrYYiqye3sexu"
    "IHpTgDuR3KLugcvzAB4f+W9X/O4X3ukHE6E/GIJqQ8Oq87F6s6KVBupu32mraWoErLdGaE0ifSK53p4Edviut/ow6l8sOrkv"
    "QucC3oeshMElfNaEH2VfLXdC2DeMQ7IEAbTVwAdMLoJsUsluVARqdnQIdr1FoOq6kTNu9EvtlYUiZNqEARofagg+PFxDcTFv"
    "/q3ED1ehVEZ5vjvBUI59HnL8NYRCN5gxcHyqEE4enMFB+utR2QmO+5mX2jTqQIWcklqJS6Oiy+ZoDh9S+eoNi+fo6BRmaNwo"
    "s6tx2zDd0Nz2Y01L093GUL1VV5+6A0UtfmZs3ZBnupMrYJqfh44uWK69PVQTBFqkcoecXaJS/pMuNbTQrqNa4R1H5dUKJNAO"
    "tQIJU8+PRwjl0YIdqqIMMcmWD8xtEPEDf6vFKFWaGmG/Ahi6rKapNp0qIcA+VcJd/TGFumqNtXVkI6mS76vr2/lDuqYl3Vbu"
    "QMxvNbWUuK9+V9dYmyqBuVLXhhbgwU1sRtvX1krqGktCYHalU3bhk/Zm8IV02T3sQcWnlddK+P8rldInPkZf7Ch3E+ASX71a"
    "/FWb1WVf1PwD43SJpb/4zx8TWI1yH0sziVlO/E0A7c+JGEG2syZ9DQwhN5l7AUiQFSBFc53i+T+fF+T/SEpQffp7AfHzc5D/"
    "Y/OVXAKM5GnBTTW5jqJ+pFsFbsUnIQ42Ig1XtumNEe0GRQQJRj5ck/o5mzRPNjMK86GwRnVAyUl0cp/t/D5LTkyITfJK4SSZ"
    "QGkneTVpkgGPjCTSAHnbtamZz0VSs+BWeY9KcZ3W7tD89Ozhi58xzc8/mrJ2tXCKV6+cM0VQZyLVXpOOLOFWkMI/q6ys0Jcr"
    "P6luppuhTA9AORM2lAVo6UgqAOJgJh8F2otYvy7OVeo8spjkzjInKinash4jTKtAbbX9xxT1iK99GJL82xUtJcn8irCmx6/C"
    "/Iqb1cZP6EEaz637YwOKVtGs50h1DK3LoLG7pKIMTmkKGkto5t2AQLX6NR+JKZWZXaZTjDMBkRrg+vtYbYYgl9xI6HZYyGp/"
    "Paa7C2JuTMJUg8BKvzYjk7ISkXojLL0g8QXY1ESWRdL9JTEe0irI8WdOP/8FpOQ4Q+W4c8rvHsz3PsptdQWDSyoXcfmzMFLZ"
    "0vTv6RpSbl2rVo2QDBkYYlpyTcFxFB2a1a/1FkyNkf0hVS0waFteKjJcFibY3KEyADcWkg7m3xnMOCszDpFext+YnI1ihUQu"
    "h0UhbkMbSDeaaihPhnhm9l/ANSU4RPihu4JackHlAdULkuoMyNAQ7ABkR1HwDA0N99BZFhRNZPwhKNlW4RSpcCuEMOmzIaBC"
    "VqoYmcJMtVIFInhIO/KGn4XLpv4qrpbwvOx2Jr5arGIyuU52vrQeakzABiAFcGWaKYQzcq5QD+zxZGF9A2MpVtKDF+pSdTcp"
    "NY0zGr4SESKIIsM7w7Ze9EYqNlCtEfs13FuUBxvvVXdOAkEyxx8Ocsmj0iWGuchYAfYZ52dnBtMp3GHjHeKCfmGH+n1dE3L5"
    "DCVmx3eAi6LeuYS0xC6TrUCDIaiZoauqtJK4mIRi2FwjbCh1Idlc4t+PoA69N74TOSkhzYXng/wVBVjb7mj5qC3u3/B9lskS"
    "FZHrN9llNtlWsFHLiblj4t7H0OKkR4DDUSdffb5FiDVccTgnACwCTyv1QINBhUaYU7EiLK5zK93S8mODbi01UaB4+w9ggQhm"
    "r9ffXzI1auyxVeCFmjsJp9UmxRpE2d4eF6vvGarl0bP2bi5WLYSj+TwECtegzlJjW7Wav2RU2LApps+xmCYwPQtShYiFyZYc"
    "glPCiu0f6+MogBt6teBKuJGnc4AJ5fv6cjtvBSDfq07cWHmZ2Bqh+oohKVYrlZNN4MLbR4pg8KZ6w6o4Idfon1bWWZR9aPke"
    "5gMGdC8WwQiZI1A7/Vsh/sDhINEqMc7atQLI09jUYNibBGfdOlWqUUEHDxYOQHSxDBIWTmpdTuKsod6caBZ02zG8EVgDlBVO"
    "Ao1lJLbcy5XPIkh2y+MU762+C7Dg/KMBBZ5H2JzShggFek0TTib5wsN9U7pv5YFYxiPEgmsaljZ5OJVULkv8sFE2XGMS6rXU"
    "DYsvba9kBf0EgR+qAdhdI/dFxkIWJi1d4OPX+iV5iSyr3wgQQgSKvL5OLRBYWJkpWcA2BTUO6OsZvK/8J983APeiCWbE61/B"
    "VAMeHRFKaRl04+9kEs6qphMiXqGBc2LA4bLLsMJKgmbyhTOilmBE8PVB5QAvkkAmQFHeyutwH5X32IOQwMaIZ2UiuMGz6s+s"
    "DQhEDdIBO5+CiAs5WWKVpKaW29UB5/ePJlEREtkKEjGWZXo+CrZv9pL0jOSSRLav1K9FIpHixsA12OvYe4rU6QcurtBl+Fcu"
    "OylOLdBuzQKx/vhpX25jH28xsWipV/N3Dbkry7DLVFyqg+NtTtElSrc+14gbLKFptfbhPYNfqHClQnnu8LO7zLJuUQ/htEYT"
    "JHbSZwgp0DV4UjiqYlzCH3xjCt+uvDTprBiSVDKjGxygqsPTwhJXDo+44qRX1NXfbWqwKobWkCR06fiNokrhGMsDHa+KhilA"
    "FugXRhrFyAsjVFGoVSxNHVwy3D5J4lmCWs95i2aeoF+EAso5jNCCmtrajQ7JMNo4s/8UfcoTsNUNLTYgM0e7OG93QewU51Jj"
    "SfU+5WdMNAWASsrrxUguqqpddZzNrXdsjkp++yi7OaHZ8lr/UrDgk2HZOayA5bVW1SgYnr4NHjHxQov7wSml/BVVQnF2bWFX"
    "l9HG6mMFwUzgzBCcNcvXPUx227UFAtT8XY4P6vjEi1AhctmI4WeFlAheQfSfZJ8QKLm3EdZB23hJt9jGAOJNMRkcOSgho3Pk"
    "QnV9fR1q6zebNQVGElEamHgMs0MzGTbhYConsNEjmpKlzUTlROo+ymUCYs7QgYjANgBHvXOqrmBtzlV5f+tWeIQf0JznzByl"
    "16IGXpi0gZrd0M/VNxieHCvGkhmzFHXM6MEwwRKBVBJevTCkkS0omkFxsqTqglGOAy+zKXwMlQ5IUrAT4DEWmGFggGgzPdHl"
    "s1QpO5TMEmnoSAFecFmlb+pMUl4jkn0aI8ykMpmalxpqKaII5BbuIz0U85agwy5yS4MxiolI9hFoAfHlkwyxTcbOujY0YwYG"
    "Ax2/YJZa1hqYO3EGENl0uGF1vFADcDQ7cSIFok2yIpkCCIjRgKydepJc89qemKLUR8NX4tqkNaTRIYAkUHpzh8bgLHzVhack"
    "JEDHPGxFNnIAt6LANaWohXmJaBo2SmeMH5qqooWLx8jU8SgMG2/iSBkO1Cm8Rq4IBAkYm1gY/tAp3dEoORMkZbjs0ZwaruQ/"
    "ROiwVsAHMtyRZQYHEZrUlZj8AE0ZBfFN4fjgqHzM5KZm0D2sKi3LGMBmx+LOPfI/9Bhw5EL/eZa2c5bhGGuB7lBn0j4VTbHy"
    "Mr/MGqeYslbh9E4ehfzbHuXk8clySlY31GVbov10ltq71Js1EP/9rsKjHA7xHyLQWstrvLcvCckZfkjnlOBX/U0UKHoXrp4t"
    "B1qU0UD4oRQjBLUJ/W1NI2bJk4KClUJIUfkXxkkdRhMKmFvVwfBYrRTCBcgvW4i6f9eMLabg2LEVHBKbGDV54iKYkU4DDmiT"
    "6YoU8AzlSC1iulYq5/qfQHjy7himBpmkJ3wZWmayq8HYAiU1vm68M2GRFRSodGPRTsO7AiBKeGVB6Jhwhhe6KELufDvd5Ag5"
    "7ivqQAIj/vCYsVymTuDKhNmo/85aaInKoWoNhtNLygeZ+GRG7W3WOl7pccbnmGehcnjVuT4h/R3uzglY83H2cNsYkAvvgJmT"
    "hNkMmHVExFkjPNmFghUEjFsUuDcc4cSu1WCVHNFe9mSFRtS7JUVqFtrhjo7zeTSyers9CDzi7iBIZKQJbvQbWBAk1YhjJNkj"
    "orwhYSm1uic1zbDAMpArZLEaocPZKzwfhtVE9VekYN1EGCxtICNSTkB2iRxfK69ozFk1WKNnB5ttOXYBi9mXahtIQjh6Bm7C"
    "+qMISKI02dKqyaE6OSjc7EQWLWlVN4EYNQcG9teo1GiBvvV+ydaTj/gLwiUMqDHB1YJi/sYJvyCAt40Df3ZCndBarSOCAoit"
    "ZUiWjs5A114Ncqfg/jalhkU2wzfN64rE3matRfUOqc2ZvMdaRFtDpab0K9JyDnrUgatBcC3Mrd4h5HPEBErM48KgWhtSocyR"
    "oaG46u88yW28I17lcEgrUCcrrEW9oXJdxZDmd5vKpMPI596lmxI3mSwu55cX3dJ2Rdzxn7o5qDD6WgKdqx87MwJWjR4wTc0+"
    "48EGJ1K71AhkkUrnWX3UUYPK3apcM/9yfJ9xiJ7lwuLdjqX3pQMgQNU/iY0L05ZrCbK9pn4TwArcrZ0ZVoy23heXbyebKqbc"
    "u3iG6FdDApzgHCDyeNOFZMI52oxjNCdFiNqaftSrwawzBiIJIHUkbDB5fHFeK6QT0R0xSNUreQ5npAhAYOloxZrHrhsL8E6g"
    "XR3pF0aIHIb4WxekVluH2keWhdNLtbGEepxM4D6Uco0bS4SXusa91buSPW2kR5RrWHmVn31PJPd4iJBD0TYEBo0XGsbgylMp"
    "Zv20UAcLtW1XnQVYMBwrgohQE3FYFLLBvRpb8HoXgiM9cGJS8hLdSKzm10sXDRMYFzvN7RfIJRFMH8LXuZ3VhADRF5E6M1D+"
    "660sWZ2mGoM631JlRvRB6mCOPW/PcVGfGxRoiZ2qsan5UzjTGv8z6Z+CU0s4x1a9+a3LbRrTNe2Bl5I1+Zcf+tN9iqqMOnaD"
    "wSU7GyhJTuU+EnHsmmQFHGK5JoQJ48ML9oIZvZKkcIghDbr+JYHqSrgttPCYB4h8LrGhJE/G3CRoFB1l2MX0G7gcUHsboFqj"
    "TIMbEgvdx/ok8FoMjegoNec6wT/+uZtOwPBp4IRWn73qvhzAw0GNSOMDzPgEG97KlAIbvvORwS4LV1ajlq7t5ZlIUYCY1h/q"
    "Dc4Y6243gtMEbk06uZFkfUgS0srmbPCoN7LZ1ggteoIp9Lo29XojAk8C+RYWD3cqlbp2qGMmf1lQbjB0b4IUUQyQ8hMFwFEV"
    "UIL7GGPMFxKw7MCAKjDmpdI/bzpCiQYQ4RGxaCY+iayT44xWeIQvNIFxJ5l5VmkIj/bkI3NPjuqzWw9BWc5SCk2fp267cTe4"
    "aVRtIvfbGrPLZ1OFQjJ0btmoq71bdyttQKomEiK3/XFrUX1m8qn3stcBRARSxPK/BB+I1k/lbWnBPYiC+n5urogKlUIHZBCy"
    "Qcdu/7E5fRe4rUjUYWBCPcPEysFzluwZLup92xzjCdZibeJ60z3lJVDDA6piE6sI3d2JDp4ffGYl41ByUBx3ziGHFjqm1hZm"
    "qJAwg0zk3g9rqBSlP6j9PCkiiAmdgzRTAJ3EAGAEJQYJE0P5LJLRYv01zBFePbL3wrBoJCXyYZLzuphxEmRfbZjSRUi3w2Vo"
    "B6wUke9+iKrErA0WngzHfx1qrmHw5FZ7S2NdW3tLuhbJIYZTs6LXtKInWeBnhV4VKNURL3ahizjBqQS8L1O+gZSRWslngGVO"
    "hvdh5HpOQoR9MeewY5XClwRUVPOdpjbXeqZwldsDed3cEbw/Wv1G0rkjNtX5kpAnWgKJtJXXl7LvB8HyiAwBhfYybK35+BeU"
    "foR3tTfUhXQJtWRgDa46yQMZo2YrCNok30gx/wODFrCVlSghqeAaDux7wnr6n6gXFlWxHBaU5IhwqLOlqdo9QKiXNoUo9h4v"
    "uZvpATJMHcVaryshfGYNgiTmKGgLeOLozw6AyRJNGwGIwlzh6oB2I15Pax84NhahxSigU1/d0mY8s/Tn4JonCDTwDZQmuT8N"
    "ZhJfWGuqFvV+GvgOCpZMvEAZQOXq5naJ+28RLSk0Tx1DOoItArYDlYtCkf3uPXNOAI5D2rdEB7y1h976bBxJUfS4S0RNYmma"
    "QRlEMECV8Btj1CQBuRfDf7/sBP/CRC5HufitWyHilgvNoqqN2otLu8owNdEtIg9jCIskg1+wWLbChAIK9f5Hnz74odjVqkXg"
    "FV/o1S5a5RlLNnDgbwwqTJF8ydwdJGmxmwcoHhlcqrryGxeHaUGb1HPkYj1WjN3gcC/99Z+//sONr/5U5V46di+4ekJTGM0m"
    "8mINHl5YDePHmjVIp9I7ATaN9nobspHx3Ef19Rt6X3hDLUYyDrQki9Z6YkujvQ7CXJNWWCNKetWUFQ0Q2ORDRd4Z4o5mKYrt"
    "I5qXlLKBdozq4B/2KGERNpTYK6EjB+6tk5oTiOBqteCBy4Rgwe4lHQ83GyMjT/wBwDkFjotIFqEec7hxEECkx/bDhpmz3rST"
    "6dXcPrdH8dS1pu+atdWaVJopFybxIb9ODfx4tp+6vYyCjdqPm5M2xsqYOqwCLaIa9Makujt1dM0QSWc2k+lr+5s50FGQW2fm"
    "Fk3BM0gJGI4SVVF4nAkbL2yZEmssw7sVWdEmrmYQO5JbWwSXp8lmzHt7L6kvG/1ITjP9RlPllB1pwRSt1Rr6wCXRwO2ulQkz"
    "6K0x6I1uBFgeYqPzVBy90HsmjCB0k9d086Q6fXZj25Z3cVEh/uAU+nQ7ZMpYQ3WrudZGoRY2Zyz79iEytExXkeQyY5pLoVwO"
    "qz9jPG9PeT2EdbipVuj2xyQuI57kghysW5BHyPKyyOWSpC6zkpG8LzW71dSWDMZBdTeTTAZmzbrOL6MBt0MmsTBFoV0cjEIy"
    "km7FOys6jxQOzOyr4OrESGYWNfCh0+Cm9GemPm6mX4uJhffzBp1JmhPrDjUY8sT22RQnqgS25I/eeajsJiFJalofsCXlAL0x"
    "NXqCPUXlsGgFN3MUgYG/mbZ8ThzmzNRCLduNJc1G0vq64EdyF0o8h0mRAOrBYFww81yRN7b+qtulyQ5iToxZ2oQUIdRoQ8FG"
    "s6OxnCLONMiR0XxWU4ToCRjHRqQOUdCnpOwgwgeQY03A0YErA9k6KTBcviBfhv1Ek31UlVXct3zoxkJbOB7Lr2RGTZcdgs6v"
    "qUPWS5mmwGg6TA0yXcqJ2C+QPZ/AxGpoLStXAD8+N9dDi4BEasQVFsTru1kqmqFTd6tEcfwl169L+5qCEzZpwP5lMg4dxi2G"
    "HrLrQyo//9Y5fC/oquJyZcffOkcEOb/LQ2MuIxoxiaWZ50WvwsA/NZLCUxGm6VRwQJUQ5Lb9zypLfkWnQXl4X5tNCCjVEhtB"
    "XS66XqSs3zpYEqIHpgLG/jvnTg5oNKtHDEbNnRComHlvUk0XVzkFeys29kkcaqYEsIDLCu4805IcmsPDoCeUfFTVgS0uYR5v"
    "nBaquZwIHujT14w1SxUygnZPFwLdRy5UQ5ouHT0BDYZ34I49ZytSCQYiHUKLUw2hHNHr0wSOP71FG/bVItGqMDUVyYi85aBm"
    "gP/soa/XvrOuU6CCaSEjgNZCU3p8xy1BryF9rfRO/4ne6SEYKGckxinyaiaAoewg9dMfGtfr3LyjTUaKtYbf9BbrnYI/iHfd"
    "1mWe0SQIqIG5nZfkwQjn4YK7DVNqEkW/8JM/9shcoXe06O7LAKL5xPWE6QbTixiDzGNRS9tyVOoB49U7va4fqDS8zFqgBSgZ"
    "SUqYGAnvCIG3oXMKt3Qi5cKAlZ3at9Hb9cgQ5PoewuNkJ8191is9sBSQxap3GEkFgH76XqIXpQQqPKwysVDkxuFXjPTOvcYK"
    "Ui9+DCTagA2D5k7WEQa14wmywtzL8Nj74CorLo52aroidEtqeUInipWEMqXlY7WcJzzPeCUYDIoMiu7C7ISe9waNPdAnVcBe"
    "mjpSKBgmEJmgjLAhUfEP6sHJZrrPDpBfMqj5wUDBC9JGrnzFDQH9r/UGV3oAhgkWwX9tRkGpuY6HoKsDtRiwCAgT4V9wYSwr"
    "N1u4kLEhhGKVGuxVfHoxVSxBrx6ytIpX196OZekBB7o2HyTCFlwgNfCaUUjJVQ8u3ZRkHbm8Sl/0M4/JHQT8ErtGyt7gROW9"
    "ivUQ9a67eJKgSdcWanW7zx2+U/WeNTkXB2nuSdVTAufnx7SIEe/qFEC7jTsXuUWK3d+qsvftOTl+wYUJAplczq4cxe7Q0vt+"
    "RJXmk8C2iuYQ3p6FoKMpO7a1jH+LXabVANGDS5qq7zbC6ZWwDFT4Je86dqdWdnOPHFmMWn2GR07p+GhMuaiuEElc2KlhdLDt"
    "Hpyevyr10CExnCrWEYre2MZ7uhAoMuXyNHYQGRkMKiRSwH3bwyoa+rxGjEkrc49F6gDwuKFXGJhbR/fEMQM3uy1IERlZJMXP"
    "pmfW11aZ+qCxi8hWzV1mcvcyLvCKkI+sCRN6QJzYRil2T46gN66BaI9pQcL4ZLkycuABbKltKraNV90c0mBg6ner5wLWVLfG"
    "bzfsUQWVSfowdDZid7Px19zmnnqQvF6In8eKwsOU7IVkcHZLtQiGCcABAb6SCOU2idD1hoTZrZd+yrVlV8Nry0xHwlwOdgsu"
    "LrsqVkRjbRW1Mvz9bUt7usglWkk3Zym2QVcCVjD52OP7crfEKmAJ7sVZH7uYq7SpHXp2cI2iVMuHfAkaxhGF8ISPB+4Fq4ii"
    "7g7jswGmmXcE9D2Ua/XsBWp0+1Sp3ye6iXBJL+0izifuA5jup5Hr5kSxYOojQpfyJMlbnvRxMRedLai+tmGGSY/viCl/19+L"
    "mxboUlpA4Hk7qkdGNg5cq/mc2+aYAYWaR3sI+zyNZEkXHKtLF15VM2depTSkFqXOXCrFyISx4CjsNXEY1iaU6K26t7RUhnNr"
    "4UXoQ6/zNbmKsj8/jyayq4vqsEMJBHiUxEE3rlRHbgRErHSilw1hJsZ9EBLEzSbUwb8Ldl1Pwy4qMDqfKoNTqRMhCLnMWLLG"
    "qXuQl3SJmrS4SrA/y1S98J68VlkKeUs0w0/f/sux7dduIrehxvn9T9h+nYPOzQQnJCgqimZoG3jLc4rwY+gKMtmKvp+w68TD"
    "B0sEKDIP0uAT//3Uz9t7AvAR4sWdAfD9IwlOrp/R/Xb3RL3HYtmI/bqxi9cVd2WiGQ57oHevqq7xe+5MLIH+Pe9iEc+bYKxe"
    "IG02wuhhZiHjDzTwgCEeFTKG5wLM8WEruLJ5iBfXoere4dOgIm0ySSRcfghgCHVceZNS92TmauKthxFx9pPWlS3zRpn5J+4E"
    "SBLB6BFmQ9RKLl7qVWCO5peFMLafLi6kWylZPappuz9fUOhMhoPLtjIPoU5JhgvlL2kwSGyGH1SRjVFKaMZVVy1VRB5HtSWp"
    "qusdTcE0iSlJhPvpr10Lmr7CsvbidGOp3q1pIP4kEjBgpX6I1xvu+XkC3pEUY9OENUibhdeS/kzpPg+PUZcpZ/wiE73Q8ydt"
    "lGkDhWtFW0SNYkNOC/1SWnJQr0g35q7AvLG3jAlAAz1FzfzB6HZRc0z/cKfuZl3BFbbUDRUVtT2VW+sv1BwZhkJQTkBrWpOE"
    "3Kl/XF+h0g3tTeRgUI/0mLU03h1ccMsSeXt4cLUtY5E5WliEsV/9CYxd58lqDP1bmh3BJQVNbJjaWtbA0lnxMnvesYnAjIHu"
    "qXoYwab+FG4PRQVRgx4pMD523xt89jOPs9y0m7/fiX2wxMEe1HMpoh30jtLExmFjFeaQPmj2oOIIbrGLWYW0K+UmPBg49DAP"
    "90SONQzg17OM9OrVy/IA0CWCgl+DH1TNDL2FNlHJV307RilXf9rh/jykFfEoJ+ntn/+8k023w/wTnZ8Iz1CW/rzNU83CHxjF"
    "/Vy2eV1rKgMSJZSSl5kgsDlkK/nZLUTNl0uXagjSLrkBFNPt6vqvpPpH2dc/cMHwyXiPeTUTHq1N3yqpakToJd1SxuBSquSX"
    "uFy6rdU8hSpLgHzAndxWdgfXN6DUxCcosX/l8y/KSq+VfvLvkJxlwKyXIRgJJ3bk/fLyT9KN9O+W4dOd9A+1dbdxsWBZuURt"
    "g45rqpura1DvqSzW32fwArdWMDW9uUopobLklyVX9FsQXEu1fbW0MmiM6WGyp2WtUj+qWitHtVbXtwVzRn0b3t/LYdn6U/SV"
    "h7VwgvdsNZzINsKbLlWibnz91wqnZpTxY7PC1O+vxweuLdxNSwiFvZ/XwmXMM044WOEfyqC/xhfk1yVXyjmigmY4ozK3UKEt"
    "LFZekq5vTZdcLo/34S4G562D5s0jGLGljwqJPzLyzkWVEXG9q6QqBLhFZXnJ/1PS2t5QZmar3YSFvvRr9vG/65rL2E/wXbD/"
    "ZpGl49+b365FBsvbnr6z38iDv75unpSvqy5Yi+zvCZsUTJjRicsu5d4rreNl9LdK7/Gtjqp7rRW/cF/5RWWHcglRWHVZAg4r"
    "w45MVlMF8JOZS6mdjLxsJ1YqM8N3OsNoG6gY1cykXo7rn6qx/ynGShv5ZzwUo/WieaquFZJVrFkEym8LACE8aqW6svjuL8Ac"
    "4+8q+4V+6LAHXyGWPKlcHbP7QoHX5ZsKXSKlQ4nVluhGlACDwH1qrQhwmlwNfQ67Jo+GFBN7ypyPAMIRSpak7dBhyB+VqXAr"
    "9Gv9K74mZln1EfkjsqT6vfmzMghCV9VWyxZXlPJDvEl9JFhj24hZ/UqhCVCWsWVawBuALqkNtsC21RFdElo8QrxXLhVdpgrT"
    "skPkpP/G78FVZPJB7FB20D0EMmZs9V+//epfvq36p/8F+qr6842/pEoiX3z1b9iIyyxO+UXkyT/eQNTvOiP4QFMAw4wkdsCA"
    "R/e88U24rXIfeEHmNTib4X/1elhqNf9qK2XqBeMreDBxJQOvlejil4fD+iVLfhyPlF2+/OsvvrBKQjnlZrLk/z+Pn/3n/lgJ"
    "y7/ANTG6Jzlr22fHz8xVwNsZZAmcZVauEecRxJ9SiHLkNgfM76IyFo4d2mSqSKeoK6PvIhOS2Y2bCFUN43XEXMuI5cUPR0ca"
    "QylHBVEYgSkUIkBVA5jRwgvFad1WdQs5Ha3FOqEGL50IMOkp2vKWXsNFWHKnHdiCKqT81LZiXaiSIgQpYF47Wyyqfo/SFPnO"
    "Z/q6xLPNyW5M34XTsCENZaC6rZW8Nl1rTjdOJ3BP+kN5yX/D3ofnFOEQyKV/Jff6mrctltm7SLmGJd9/+snVEolwag0fRttK"
    "vrpRYrCGhjlHznVp8x11P5eS+TG8YOAzwoyoqJTKSMjAgIgxw+K3kLEWRiLfQgw4Wqie1svyZN2ttirm6/0QcyV8GjdKHHXQ"
    "FeLaTkyh0dfDc8ZqfvzCFTzxFjkQlw8oksm+iwSf8I+7yNesN385ynV7C3Obq24DNKmOqJXcZq+xuff2rLGQ0hsoTEnigQMg"
    "1fMDO65npoUXSEs4J5A2RGYg1Jau+a4ZC9RWwJxc5gNdu4Nr0mim2hp8o7UQ6X40vJC/VOgVVO5EHFYZ3E9VSjbFiESaaxqK"
    "J/nTWTd3NbB+DbLQ5tngm8gy2y+ZCKQDdQbCWbe0NxZO1zmkVWZoxg5J4WegGZG8sd15zXKDGANJZecytO95l5TkG47DcHp8"
    "KWTzVGfqKCRbGN0su+ooV67kjWrMwWLd0uHdq+soLS+/FJMY10s+lRGSNW93whInKUxuu6PT3B8OWWw71clwr/vdxqpgucpa"
    "I+LC2iEFT8XUdlUlOTGLX4mr5xxrZFMqP7mdbiur4RnG9pTLX6hD11rXRjzUp+VQMyGJLMam6l9v/PXGt9FmUXyiRFoIdI9C"
    "UCjGFVfP/9/rJVfLrV7CNzmPqGoSUBkXljQS8kNZGfmzMVkDD19ORSZtZHbK6hO61A68pyX9H+04oimDx7mLcm7Y/pvgluiJ"
    "Y6xohBpPVs0/ygNT4G7J9aTVbU23Ye+q2+vbyuzopTOjCcvniIZLDiEjwBd2LKU1qsDWFOivPC/N6Zo6YUtoLXEDLqRLoSWz"
    "8Xp6mcQQfG5raVe7vaM8mG9F8HRUAYqvdOKPsqP/dStQMPzI8IigrP6hyv6YQM/kgeCK4Krpc0JfF1noIm9WCRkFwlT+oDCt"
    "utlee1sMABqxVw2Z/QpE/ZvflHwJMvsMZuxlfCET0k2oLO8ITk2xURQ5RRWlVUZK0nTADhS8WIEWaWUHHKe5/WZ9XY3yQMcQ"
    "CYy579I/XiuphTJQ09T8Y5kYV+XChPCDMSc5Pr4ZYPOCw44nPhFG2noX1SXLSqtKy2n92H2xWq74fIZY93Ll8BqA6xL4ecWK"
    "G4FrETogFbB+gE9H/k/nJP5lnRX4zA6RWTVrStUjcT54XkpplzA3c+NDkhLISpKsdKNxStSYlqRzqZU+gv9S90NGpwJFpcCv"
    "PwZ82hZDxcMLzK1EUsfEKwGJrWBgKR0c0EJE2gl+Hik/v0vqGBPlMxqC3pQ6hvJuChOiCst08yrRZko4D1iuDXXwZPFugY3l"
    "MnGSviBYfeegPEXpKB4w1teXZXP10GBnC4RJVEaASupahfVei/HekB9/X5cm71Ni0D0vJIFImxeihaDpCihrwkeul0SIwyVE"
    "PhdMzKo/cadZhZ2BYTwywoDx4DXHmI1WtJbf3K8qQ0em/CafXW4aq0wtD7lfVRoeh+T32qpoyWrtzPkq0q59KVCQ8bjKbP0C"
    "7sPywnGkzXTNTiSoirHBB/2rOQCP1TmuhYhzTEavnsHIOKq/B86awPyqn9g4lIuPeIrtPz/Z9XjRhotNMHQaWILHzxGHaUDq"
    "8qRlq6pYk2pDJU71XFUiovq4VZKCZz56JOU9NKXAvgrzXuBy0fZMtICKY+WlyBz0F05D2qmwgYXKKMCa/8CIrAISpoHeQmxg"
    "mT6qFBkGEcpLtG3jedXYBG9xwMigRfNXMX0j7hOqnq4HPFSfdDiBe8U9zb/8pf5YPLoQUqLqQYHmDnVUXw1Os6i1wfQ6yhOc"
    "mHZZ61TjNJzELJrlJSYCZL6Wv4R/2GiN+WSdfxKWqKquiXIxMmZd1yTzqLyAGCoYBGITVTLY0rj7Q+y+alQUM6HF0LmBv+P+"
    "po6OSkc6BBZs5cc7TXOLq3joov1FG4zR+0ebxYo1tabN45F2k106et7k3cLe7P7pPuCZ6Pl06L8jIQ4WH1o9R4azVNWo10YW"
    "ztnsbMn1iEiKtBIK+nOmhzs2eXkr/Ajf/OFG4AHR91sBMfyNVlf5DTwXgPXir5ofkY9V4gFBsPQ6xSIFqh91DsQyElCL+Tuu"
    "T3OLLoe0Zt7jbdlTO0gu+p1Bzmi2iqRSxptxPQ2tNQgUwtiGlwrXqQwALY6LUln/W2oPlGDUsZcDP4s+n4Jb8lNoY79DaSLe"
    "aolqM2Ob2YWu7NSqSZDitP/8zTf/I6aBlxo9B4DLdKS5L6U5JLDlgZ1EuhTA1ki8Hn1JLJG7zXGCbm/UfWm9yMZU2Hkb1Cr2"
    "w6TH/RjxTZdifvEVcLZT3zRbIOHfCy9tvFWcXdxborCtxSe5nae6nSlv/DW8wEzKyuzgjgaFlGjY1oRwD09LC6MvzVUyiF+Y"
    "vpED+AbQqHdSNX8rm3lwDQ7P3/COzd/Imfqd9+I+GGX6bmkJHsH68GNKL+Gs/N0vinHtX+hWY6ug90ffSpWaY/y7isoSasDz"
    "z+iTPpz3n/XRCdTFeydS3kkPhucPAVs8xJQ8ZKB1LfzinH0+9xinjDQ3DKy68ccyCrdQg0lSsAL5GlEPHLZtuEIo1SLjMcqj"
    "3fco83bIIaL/dkTllunCyBm9wSZddqtdBUObhP6qySfNsMiiwl8tv9ZnnOmqo7jyPHc1bh7LPkWqz1tYI8YfrScz2SlNLi0f"
    "RRmP+iyMP5dS6o83/gnqjWh1oau5MuK2NR7nUNLHXc8iz+zflamYAzqmMrpNhw5pV02J+6YLbWj1P+KTWT5H5znH4ywWlPON"
    "TiRwJbtSOe5jjXiWrbXeWlHwq6uyuy7eBGMxwblrW9Z4QaErTIxBaI/lSd1URX3cYKHtEis0emGsLfbfhvTgevOEdWCUpz6q"
    "1KtfCBKhQRBeSd6gj7eBE1UXGjBRbxhUyY+5TC9odJiY+3lr6XrUJXKqVmRFxMYNwDnyf8pLJNdYA5L/LzZju8gySwnMMuJP"
    "Nibj028MLCC4IcyOrWirwebatQtivpHGw8k7BqEz80tF101mXWZmq9iHlE5UEkcDQzEwZ9wTY6M/7kExX1ZW/PrLa0J7QcDI"
    "fUi/C55x4z01PLRhyMl9KfgWr32hTf87oGWN0P9d8nYfLC8aFyo4M86yxQ+MwDiKHxY3UM5NAtXVm50Kfqgsv9AuFe8Ci2Jc"
    "HoWcI7GpCK1HA2DxqTu/FkxdjeK/b2Buu0UG5obfIsI4qraR/QZ/ufQXD8VFbZFUJGxWwMv5dUAgHVGL1bBwkeS0XeXPuK4M"
    "0Dp+tg/do9GoFkAY9FWx096Ax9obGvQYFJpdf4fQtjp/oaQrbD5RrsccaUmnoLCljyx44Quy0vKQMFpSy4+BXS9HQr4xh8I5"
    "31evVRYYkKURW19izoFJrOoPGSIdKbwYobZU4WkFDoJYm3er66gIUHt1W7T6gYnGndNDhdF6zJZj3EZnNNOpQtH0mjSjotW3"
    "cBgAY/oPozIiODt7Ak+9h/voAJlHhT+o4bjibwzJuev57nVUQGG2Myq2nM6kEB5H2QtmdyNCe8A6lyw4NfYWiFzWlnHoN5ll"
    "2s6v2U9Mj/9UbuULvMG3OUwQIZRb0hsCuDTOmFP/A/64mcYqpek4EpRBoPg6vViF3IlPp/8jiTGzb6uuSo+W6E3X1jDUMYQt"
    "Gh+RjkkpuqoWya/VUSfVr814o4iLUH1133GV2vDFy+6L52iWjvZn1z5BDSy3K2eYjl14TqVKTJQyNVRSKpUR56praA8CSRof"
    "QFhVHhH3Fp4qD0wNEz5oFVuD3k2NNYvlARIEnyIZ2rtPW8STyF8v09vLDZLfEFyA5x6Mmt9GBxBaK1E4MACKGEhHSX4JOR2H"
    "lwHsvmde7ICRWxoxqyJ9JA9bTpW4Z83y4JE6ZlvT4/YdKVRXwIxKyCO6LIZ07NLoI8YGowPo/PkYA0zPGrAIKEkUb0t8s3T1"
    "lCorZWgJnluu+MciQkkdEmiGwmoayxrb5J3kJ1L7TmJRrCmVYSFAf28WCBripiSLlndlomg5Em/hQUBeaebQDDOJoJSAeXvz"
    "Oc+4DiBUjPzUztpdXHEglRdQmj5SoT9beIO4mS603Cyq0t1z7kKHTiH10+l34qpznbpiLhpErliR5xiR7ElRkHRskr+7Uw3c"
    "Sjy7nGi5CyzWBuP7W3SWyFOg10f8iHqxtwZZSyONGmq+ro7E0mi74mSMkXrE/1geh7CwmmaZ/GY3DMYrT762hTP+6bUCsZ04"
    "frcjetf0tFsfZ3zjZAqBQy/sItDjYrNwfDURZS+yNjFW5sDyDTezjZ/vXbrYZvFeMvEN6qkzHkLLs8XrzOjHRxhShWFGlRda"
    "HsMlwxyCCy1SZRCHKezDHJmCHi4XPtrefFtzHwue/RQJE0nhQPP7p1iTf8SQ/2fVt1//27dhUTt7zKroGBMgoOQL4UZM4FbL"
    "7jV2/OYenEEdcDKWp7DK4pF8wozYoMIf8bCo4NJ3aFldmTnv5ZbnlZlxl5v8SCnsySsCDbO0dUR0KbBnqA+UbkubnCnW85Ny"
    "LCw7iswtFK1ZPS5D0Rje4H744upvUGZRb1pFm6wybGq2X3Lx8HaC+bl+r38GY9A5SqVK0wWTE+XXFO92eLTCDEwpYoJ29Qen"
    "XVlqI0RNVg8T4WSgOm0dK9KkUGvQeRGno/3WrTpJ16gKFP/S4BJg1kZXFLJWFEMSN66eLlMo7D3SUIfFM6cUYHFPGumIwpzt"
    "ilr/OO8w65LLi0cz+qItRk0Mx/EoygcB8JzbOJF6EsZJXmJaQF+drHKrAhB4wD1TcMXG+W6KS5cyKzxv0Ej5bRS5EBJihfxa"
    "+QmYf0N1W1nj9YSwKQK41c3XIy7JC/meuFTXE3kAk0SwYNdDTTTKMmRQ/wU8Q2RuUiAYHrXCXChngeLHMkHeFsjZIsL175St"
    "FVauVhaRfWYAMscggyNIVlE0ZIyHm6nFj3hy62ZSqh9r82FeCy2+AhKwbp0fIo+qV+eHwpnLLsRBnLB4ypOHHeEixRlzoF7G"
    "oaF0oP71j9/8c9Wf4K75U+GGR5iJC1wyltLvz5NmUcopYC6X4pAKpXXYgfU/JkVLUiU2VBPriORvzafwzfJ4KOW/2ZUNLG6x"
    "0S8aaIlr3nK7SYj/N+W2UbjreOF32eOHqHJ1luk5O5nHhQHAuYVajuMUwIhsYsBHVd03wDoLH5/wF5+GzcV0m4DB1dbVtH3E"
    "+jKxLVpfxPFtHuS2l8J27Wor5UcidZE0uWSoQvF1U1H0FtciPnbUzojr5LrA0N3fCoIogmz9GTGrojGHRJ/XxX1mBe3Rq62v"
    "hv7ty5X6V2ngNQp+Ck3YjvgZak3eGBf7cS2u8/7UrXF0BV4cPrNefIMkq6LoGIvAV4orzCXOPEqymbe4r7DU4v5Dr6uLUL8w"
    "VCeyZjxyBSCdi+j1eoNHNAeCqga4cxzHEy6aIH1iFouLATrPSpEnog4X+SrwgVxg0E5XJcTLLr0O0qheQ6XCZJC0xvI+QQrW"
    "R+fTlm7EkLADnFRZUkJAFPtUx1zcLyjAwnSQsk8JnyxPSgW8Lh3AZoDh8Cvpxn0qaZsLSTFwRoZc4RxfeGS00bOM+qORlLPh"
    "e5HVr7j22adShjSlSYBYSV7hM47bSYauae7fPU6mQ5LVmPV3j/PpKI33YrDUDlUxW1dWBGm6VnumTaM1LeRg2guguJoxP6Sz"
    "th/hHcXPQTJ/cAZp2DhSEk/7WBqvmNxwMWRuApDzvaM5KK6y/mN4teJ8hKU0x3E5+RHzkgSFklIYkwocKSs6BM83avaCy5Q6"
    "HUbHHUeCOEPXnxIHHbYh2nAUX+aAmtxUqGI+ymT2xbE5zcay0jkwJuok2gtxD4/8fjEXzrlGVLThqnB0SX1TvkX7rArXpXBN"
    "W9MfcyCba5Vomr5Sj+u1e3a5OkqTU7wSu7wWdVlaUyrQDMvOg5l9TNXKnT4BveGGCIwxPzce88dK+gPrKP2O5aImN5jMptU4"
    "OsfpA5AcNjMXCY3GRIoC3FJBSQVjG8ceCmxu5pupZAWwLC6cArBZKsB/lRgAWEmAALMH3RFV0pKKKicpxjRfIR+sRSqORRlw"
    "3LFoQwo6xd+rffKPX337hz9+ZHX1hTCK8EXIjqQ7M/V4h8E6/d51ZSZ2EDypXbiQvqKKuFkTxrRFfhO/9kNIS4mL65qFfP0j"
    "VPULs1tmWCVRFGCJixMkRW10n2XeAC2IUklykQ+Rg8XRgAoJtEhC0GoUR6jQwspf6PxrJT8VVTFa1a0KmcI0TQu+TBUG8iwc"
    "vipMElW6CGd9QY7WLhYdnruSULJFhUlE9JONXlZd+1PbyHewbMA0GlkPp3hTceZAhiwcIN7cfydOkvWPNUaxOu2h7iEqABwv"
    "0KXXz3QruTpi+3csPj3F26+0HDFda0hpRR3ZSdBYfxCjdbm2iS3bCgrRsf862SrH92adfh9QftypwN3D1G0flmecU/zkVn31"
    "7Va7RUUZPwkkTFK8ACg9MiLkBdXgbIExnTOSO3W2nEpZAG+y6RAWxe4ePIkjBhk7wq7oKJEZVeDryqTgDXopMkj8UmR0eE3m"
    "f52Zy+zCvFPneh2vRUiHflZekYtK5F2PcWKvgXZ4wd/QI9zMgYJSWkyRZbvnn9HNTF/w4hyxu6eTcHiXsh7a4NPSS3+HWNfB"
    "lSebX/eCrFFBLcl5lUOufjN+p6xAJYk2JQmmwhmKZXzyWROd/8iopChOwuqFlnMxR2zprZamhipFFSiDolkSbI19XXBMVUXA"
    "B8WavgPwmxQkFXSJppGGUJUQvRWiKmQE1y6WHKV1gFRAk3xFnthvDCW7XxlpYgElyWdTCU4hCzTnXI9H3KRQJm/xHZpA9RH7"
    "StUVE9F2fXRJEIfIw1WBkpOQ6SwPNt26JU26zoAkzhwLhbou6B+KuWDZ1g8X8jwHo7inPyZX7ImleQTNRb6uNBUTDCu9J7sc"
    "Vq6QHQ7/DDBU8ncAQGtuEolbVdtUJQvgHh1pNzEiL16sSEQ+ltTsOrucKIN+EdjCmm/TcLNO8+HMnRkVSe4B81RpKpTJZl/L"
    "Tbq/edtk/MefCkWIAsh4yjjthuofb1pz0k41fMZ1SctSoZ3SEjo7wmeiIq0iUHhdb2QxXeLahVQR+xBMB5hyJQAIl+nzqRI3"
    "6pPgGfn1dXnJFUTSyO9Nh1GRFAcmCR4nwVPAtPfyhJW5hcSRgYls96CmqeDOMlQ1vKc9OXE+b+NJfq6HP3EsEV9FqTsJg9kN"
    "ky5c8JZh+7DkpEdWgdbwYZIXJIW7TfyFef4WzuMX9MMUv/DFZNvK4OUAYqgRiY5xgPZ+K9K5YB0Dz2w4eOPQ5VsoH/BbTuFO"
    "S1P77TtV7rQS3MiXEvC//wUpEmEqk5MQkRixtLUmGJViQEr+rIwwwqIQ+IQOL4AEjUGIk4DDHRGCF5kSVRQLT5xRs6P+gYTH"
    "gqJ46hBIlBdFkUlEujhPuACnIgzT6edekCxX2ElI8hcDUimDT4JYxgReyhzgEG5pmO118/+UHeH14IOzqcHGXw8+pFS+XZf/"
    "JjxYhUsHUX679vq5cj1eDifg4/DDx6R9qIGFff3yl47sCuq68ZtAsSku7i4QHnfRXj9NHTgP5PX/G5Ap8jXeDv4oIi8Sy4k6"
    "aB9dHvh9VX4mli29JenlZLeOFGb1yPK4sKTGwkG5pZ2k9YInjfvguv7sZKUogsA4RBILh4YCtCV9q+4HGoasUjX2ECmUKa0B"
    "xnK7x1O/uhIRRrIn7jiF1gyIR69kD16fQi7m2K8uR0RY/G0HQBHhdtzxMO0jjsCTEYva4R3d520epzOK1ma9FNxmCq+ATOQ/"
    "j7p4oRcyb8VHzUpnG6yO7+HmirVZb7M3MrbgULD08b2kLf8FNVFsGUr3wi5kHEPXPfgeIQw0eE/H11ES/Cp2Cnf6AsiwKN1d"
    "jqjbUQDGrwp/1qKhThnIiD57q1QrXHPc8rwz7JTFWpmfbE/4/TdX41tYOJrrBXAQU1ZT64VW2iqgQQXRqLkWVqNyq1a6dUML"
    "6vbGknuSQaC28pPz4PXY0M5/oUqlaGikFeJSEupvRuJS0VMdCccnadJ6evIvphFb8YEQW5tN5RArPZm5kqwVuk4gByITz3v6"
    "4dysp/POW+Igo+dOxynHjbXrWeVTglpkCLw/tlduMO7E2Qzrq8uVFOYalQTKcYj56qXkYUC3Jt32rOuR5hUKAyN68q8ZOtZN"
    "tofPOebazKWPQX5roqaza3lEgMBxM9TxQOnZ4v2Lhy8QnsDSocZfdglXej7hra64wR2IycweFHWEM1L+7P3czofss53wIsaZ"
    "Z/gBKEM85HU+AhjTdWTiyqh6rcNCGwi1XoISXZWp+EomcZG4MhwKBuD1gBJpjdXvlfrJsbpcWD/3CxJajcoFt3CufF0RFBar"
    "dPlJ0JVA2ANMtJlYgRnhHDZ59lxzLcIlz6t7V1GjikkBXwp1+6S2bI0zs/6oRR/59lfx2tyxirst6Qao/U7F3QS2fa/GsmoY"
    "iDhM92TerimHGyk/bCUxdsa6hZ+wtMDxlII+C05ckXKOxU+MEF5FWIIuJq3s4Msio0ctDGRa8Wq74KJzelvH+xX6GmgXtAYM"
    "QSSwISGraKtrA6xrKxU9vK4xnJOUQZjgupF+XF25onXEHHqLDr3QWI1wOq3ghjrAJ08MVOCia/cRThNkTVwrYCmmQHz0+MJC"
    "vlp+6SIH4SI0ZpUdxFWSCAfBFYbn5P4mRX2jJsVMnPLOJ6/IbIMEnXC27CzOXQNv36WLL+8tgCke3uNrHerJNxdgzTxDXDil"
    "VyBp2TstO2eQOYQdvnCrzemNpAEVRjOIVMnV+5YMZU3LzRlyNT0v1xG8l2YIac5SSHRJuNdrMdXNxb4WQvaKszS7Bkl76E+e"
    "YFL+y21cXJjSy+g0KJ68Q4W5BzRxaPsXyz0o1Fj5RtSN4IJvC2NW52VpXXT7EeWLweYtOl/NrWAIWBUD1NfJnxOfvFR4xvTx"
    "S9HDI1ADzajg1SQDp7ztz7l4R1XulD/8nKdHm4h59wIgRboGoKgQxiPJh+ZOkesaTaGTQz4aBS1WNY1htmht10j2t1PYVdp2"
    "8kMLqwteqCbYpVhR+wIMqVta2Uyl1amq3GHPh/kxIVOPwrTQYR1Fs/AZ23xlhfmoGLgf2sLrRFy/9rVza/EGIc4Cz7pFKLDU"
    "aSE4uzRS39iJnKbMZkEHMpfXOiUl5ad4UcSiN4+wVVPXt0zKrn5WXljetxhpBL74wiBAEgHa6dqKYrbIXsRkjUWew1K5t0xv"
    "PIdOv+bSDHO7ApfnY5frVBWrRNCRwA9w/vb2YHrkZzJki0q0Dl+8FnxF8sBXJSg9ilzPACfEskuWSUR5gLNT+m2IACrk0s7D"
    "zk/2jeQTX3pHvONpXnkfOW1Rx91Pn6RlNEXwgn93Vce4e9fWrpM7ASI1By+AO8T914eTmoqroEMjRN1Cj06rwZ0cEQiXlsUr"
    "P/cgFKKMTCFGixI2nRmYUbyy5MenAkIyxbv23yKxDJKXIJXOgfzSgRlbU7NxXsYbr9BPJuyrQlgfjicZRjJI+NNHxmUKpMGu"
    "3H2f0jwLJXivZwQl1CLDw2K2VhnPrvaeWCYzrL5ZWCkzGGbY1E/PmEpcXpW4e++Q4pfSUm6slQaUkFyYZjr+CfH4IlpM9PS7"
    "i/Dx4+8+nXT+g0tw6KaNQK/d9SoIuEfdy/YcVDm1WaJnznEamw4LLutx1rolvK/n73EmO1YrYpBMIhwfVYdMEeNUNXHj7BJ/"
    "c6Kzy94EFLibl1ZpcfRvqfVRYODps3+Pc/kcJ1ehc7k0xCvb69+4XLr11wqXJTjEwcOVYQMBb7teElx/WsTWSzCzS6WG9pre"
    "KgdPAK9vHH6e0itG3VvtrViLaVC2IVcG2uurecms+PfBz1Jq6RiHulxUYRtNlmgBX9VO7HEp1BlsRPEn5R3ESqvGAnfh3soD"
    "1/VODvhirwuJpITkr/M/TkhPte0g5FdaGm9F4CnXYyqyTvN6MVZeYWqahZmoBeD3a656lxTOKoaPlWUOxJZT2NHGMC5W+yFI"
    "rjednF9++2P5DdJY4ARmBr9pmPWm3YCaK5DLEg/r7xMqjMdQm79PKFgeOdUJ13n8PqkSeflHMxV58unGntpiOryehbcDMCuJ"
    "DHaE688VQUUmVGQ3AkiF1dl/0hEqqNV5yUmqAR/Pdz6GOuaddN7jqAIGTveHYO9xHzDSyDWHJh4vLy2NnavyS/8XBSg/Vw=="
)
_engine = {"__name__": "_night_shop_rules"}
exec(compile(_zlib.decompress(_base64.b64decode(_RULES_B64)).decode("utf-8"),
             "<night-shop-blind-rules>", "exec"), _engine)

_HELP = """口袋夜铺 · 你是独自经营旧物铺的店主。
observe / status：看店况、库存、当前客人和 legal_actions（可做动作）。
新局第一步：掷启动资金（两颗六面骰，十位+个位，11-66枚古币）。先停下告诉人类，
等人类亲口说“掷”，再 roll_start_funds {"human_words":"人类原话"}；不得替人类发令。
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
                   "roll_start_funds", "work_shift", "run_shifts", "choose_event", "unlock_location", "close_for_now", "reopen_shop"}
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
            if action in {"roll_start_funds", "work_shift", "run_shifts", "choose_event", "unlock_location", "close_for_now", "reopen_shop"}:
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
