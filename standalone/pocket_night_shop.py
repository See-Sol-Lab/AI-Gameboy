"""口袋夜铺 · 单文件盲玩版 0.3.0

给 AI 玩家：你需要有 Python 代码执行能力；Python 3.11+，无需第三方依赖。
下载这个文件后即可玩，不需要整个仓库、MCP、网络或模型 API Key。

    import pocket_night_shop as shop
    print(shop.cmd("help"))
    print(shop.cmd("observe"))
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
    "eNq1vWlvHFeWJvxdv4LDwYsiq7JcluStVdYLuGvcKOOtajfansYMCIKgyJTENrfmYlkjCCBFcV8l7iIpiZtIbVwkilty+THF"
    "iMz81H9hnuecGzduREZSUrnfKsNOZkbc9dyzPGe5paWlf+sY8EaXc0uD3sp8fvzwbx2DP3/6yeX/PHr05aXs2rA/vZbtf/63"
    "js6vvjg7Hvbn+/OzY/7CqrexdLY/cnY4kZ/ZzU+eZg9Ps5nR3Njq3zruXbjwzXcl/symN7F5tt+RHXnubez+59Gc39/Btx+N"
    "+vOH2cy4/3g+O7GNDrzXY17PW2/jEV71tiezK4fZl5ve6At/ZNWf2PW6X3lHHbm1e97mE+/hUH7x0Dsc9adXvdNpduX3H+R7"
    "R3OLQ97Auje/7k9teaMPsiNbGO/Z4eBZZhcfcu/u+4djuZOD7OSQt3L/7HAldzqDLrOvp/yFrv88GjrbH/bnTnWg/sDqWWbP"
    "75vyeg+9iY3c9Kg33smeSktLL1yoa2huamkruVnderO+7tqF6y1NDSU1Tc23S8wPtel0M/++cOGHP3/3Tz/+UHK1pKI0n7nv"
    "z4yWpkpK/b1trHFp5YV/+v5P38lvren6ev7Skm6urmvhp9aa6p/TjTfS/FzT3lLdJp/am2+0VNfKx7a62tv6Ss3tmnr5qrau"
    "taGutRUN//X77/+H9urPP/FOuvnr2f64/3adn7IDB7ntl/Kp61nusFM+ze/5nYPyaeqN3yW/eifT/v1RNvfN/6r64c/f/0vV"
    "X779t2//gnY/l6/+9D9/+PH7v377r1X/9t0P38ksv5Lv//GbH//0Z/z1xYUL3/347V9lIBdK8L+y0lvVbTU3pe3OeWyUNzeX"
    "vXeQfXTf7+jILcrg8J/s3JTX0312sub1ZbILHaAeb3TVf7Po9cx6G0N4Ot857r/ux3bghUupki9S0jqGvvYw/7Av3zsMAsi9"
    "2wIx+NO7KX9z1Ft5DlI6O3pk+8RO+0/GzvZfnB0eeiuPMBx209eTf/iE7ZanzIB/Sssq5zZW8hOz+el19p65nx+fzz9c9YZm"
    "ZSobXX5HBi3nF57mTh/kZ4eyE0/waH6iE917Jxv8B+TY9dqO+PNgxHg3O//Ef72MDrDcaJ1UOLOJ11O5jiF88udOeKSWXmKg"
    "eAhPZ9e2zo7nQaR42pvf8qcOIiMG5bRc57jyc+sy7wf+oyku8fSaN7fj7Z3IJh+eeis73kkf5p7yhndwFLKTs1hsf28R/+Dx"
    "7KN7+WezdsSfBSPOLa56q8f+fIc3NoIlwwqatsZGUto+ljm3gSHihHdgPfCQ/2rRH1z1B7Y5jP3n3uGzyIiv1bXUyqCODskp"
    "+nuzp925ng4+PH/oL23l958oAQ9kd9Y4n4VF6W2jC1358wve0DSOtTf6klu4vKVjvpgq+SoYM8hBm8wtd2PwfNm27E1s44xz"
    "Kbt3vY3HWHGZ1RusDXneo/u504lc3wtvYcx/2hsZdn26rS0th5WE2bfF3ocH+MbJ41zn0Nnpohz2YKXIncDO5vt11bCj3uiw"
    "tzLs797zR/o5gDEwwWm74pctVR/ue0dPz0438DCHjjdj7/jvNs4Oe7y5x+DI3E2lIYwKYwDZCFWBue9Hht+Wrq5pb9Yh9mcz"
    "Pbnle9lDnsXc+EJuaNdf2JTfFja9w8nsRHAQD9fQuPd6BuTOR4+fZV8mEYm0BVLJH4/Jaksr+jRP0MMn3LmZE3D5s/1Bbvro"
    "a5yv3Gkv59Q3jScjY62pbki3VMtSYwkHh7Haua4h75gElZ3bx2bKb/3Pz45nc127ICF/cstbG8xm+oJe8E+XpYx/CAaan5wH"
    "7dq1ZdNCDNlXr/A8ll27SZGmj19hfHg6Oz/ojT3Ao/6D+7mO7igpG0YOboVVBTHmn7zllLZG8+Nd8sODXsOW8rMgrQfsq3PL"
    "25qRHjL4J/sMvGSrkLmhgVzfEMc58oQUlRl2O0mdHfcY0do57a1sQ1iT3Y0NoSsekY0ur3NUKG8wyi1uNonsALvk7E76cqfz"
    "ub1Njnl4EoudfbSRfyxyAf/BHnorB4YSsDYrL3L9b7irq+t2aS1r0+eVXYTHlWxyeh3HNdf7AguBRcVaeqPPhMm/wDuYhNIW"
    "+Bp+ig42na691vSL8Aqw2Ik+rp6oDvnxzuzcQ/lh7qHIDzKzK6DV3LNOagSzO+CFfv84tAi7tF/aoU70gVmTCo54WFNoI98b"
    "ntbsm4dm5OCoyzjnr8GEcgPH7H0kk33YpWOIMofqBj1bHZP5DHc5tzSVHR3OdsqpyvZg1zfRFVgA2Dz3Hsuxt312uJF7t1co"
    "JsBisSlQhXQt/f5h1W+4qNnuNbzGBYOw6DvNT+9g7OA6ZwfdIBAe/6UtPVhn+/O51dPIMBvaW+tqzJJ6W+TVuYF7/vSgdzIo"
    "LPEl6VcXFmI037HkT+5Aeqayzw/BrXmU7y3jDUzgLDMC0qFidfQUbKiQCWe3oEH2hjxBn+YaHh3iMJ0dPDHUuguhtJ3yukCu"
    "K6TAuYdYXJzks8MRb6zPWx2NzOBGfdPPaT1yJ9jy/Phu9k2/iju/f9BbnZbfhnq9rans8ro/DHVoGm2rWFUOnFt7hjXyZ554"
    "cycJa3+0QIEnLXDc2oMShL84lF9Yyo0d+31jpGAsuSgb2aNxv3vJG53xhkT02qbtsBub2tLXmpp+kpO1+C77tNPreMjxQ4kG"
    "sew88+dfybncHfBOSJTZ00wKCi/1OaEZ/OBPPy9kE2cHz3L3ByybkJ2aPc4/m0Iv5G0jWxQVh9Nn+xl/ZkQOxbCR2PuDQiQd"
    "2VcT/sQmHo6ytva2tqbGf68WiQdB6mcWVdXJHh77/cvhYTgeM+RCyf/4Ub7rmHuZGaHgGBvyDnbOMnw6t7jszw9DMPmDPYYr"
    "RYUIGoJBwlNpGEj3Lo6eNqp9mk2YhkzKkNChJ532gr14K1MgJPBSf/KNDioq+eoab92sVp2ZTYwe+FsTpGUwEbC7N/syw+4D"
    "9AbF37C7rVH/4Yb/bi87N2Zp2zIQo5RsDHnd67RNlI3Y9kSaiBakHFs6NPqd6h+mh413/vGGUWEw3EpVoKv+v+/+WdT5O9Kd"
    "UaKvYI2nd3HcOVqqqfjCO36IM2XsB2iB+Co/C71XnhE1i2+J6lOqYw+0mCvUcbe80x6xLVQ1kB5WvX1ZDyOCI8+JtGO3mxnI"
    "m6BFESl8DpJkcUgGY/j2FeXbk6f8Ujgkv+leAyHyG8uMOOwnb88OxoIm9ZBzPHKS+LA9QOxp51l2bkNGZIlUBr8GIlNjyey4"
    "O/27Fy4EFoxrotQ0tbfUqV6XewfZ+RK6CWUced2Gtyfd+F1v/f4TitPMbq7rmGsM7Zwi1AjPwFy+V2rPZWbKHxhQwekPzKiw"
    "hfYNqjCK1Oq6P7FK7nTSBz1XiazCWcVwt802V4IIP43oczd13PmOjrMjCh2Ymf7TxVxHp7ffZ8Z9drBlxn06g6FD64emrjoE"
    "zF3d24issDS+epCf3oBV7EH6dPdBwQIjOduHvjGcn9vNP9wWFUQJ/OXQWSZzdjypreR23tnZWNoxG4w5fBVKo3TNzerGuhpZ"
    "+6UpnH4wdf8NlVKwgexYj7e3aqYBJQz/5E5nwcpE3vVr12pNeaMrfscLa0DE9gGMKNu37W0+9B/dT/nLHf4TyKTT3PEGzbXh"
    "nfzCY9B8rmPMO+0Kxh0QjaV1rv1lO/BbdbVNt1TcZ7x9KDMr3Oujx9xZLP6zXpBHnG7ywDnG+sCeVWgL0fCwFZIOVp66ERZf"
    "ltNyRErdfTJvb+WFN2bXODyz4dk3hwyj/odQm2prr003tgkXBAlAvZnp9FePSDavn+GcSgsw4Z51gk68/Q1VUbCDOG7AU7RJ"
    "0Ew2s5bNvNaDnUw5AivpLnmrU2g93/sApknKqJTDsBrfgHlDPmefn1pSsYc65BCGe2AaX4Z0X11X3yRk7/ftePM92fkjaPVc"
    "+eVOyG4DfVAqbGZk8UeULwBGooKwt8pRdRstvXDwPLcP9nlc97v8qVniR0czIo4glk86/PunwEhgXijhGTt7bzXXT1jhLDND"
    "eXrvINybgCWZvSEdXQy3xM4FTEAVuNxaJ6UO2t3awXgLTnHXcW6zE8sDPgGNGVZB9v6utc8S2VDu8CVNacjrxVfefifFsoIA"
    "oFwVdhCw3ujmWQYm+zsceBGNu5C3CTzJngvDmSMUBlyqRTQcSH8f4n6xL/+sx599BP7F/ekc8h7MuMdiRFkcwTrwieNJ4m9i"
    "ytgtSmRLWZxfIEIyV4zL7+omK5LTcej19mQXN2AaZ19P4ATll2a40ar+TJx4G8f5pfvZjelwfwIeG5Kfc+IvqVD+5q//+N23"
    "//yjFRqEWrA9kPxEUAbnsv1DfmZHdULoBTCuocADcuiHcCDeBJ3l+Xb2xTQ5KYAn6GOy2+G0gLJM00BYGBUe25GdG02dZQaw"
    "dLnTOUWhiLweHkK58jcnvIO3ZBxzO/6b/nxmxmkn/2jCW+6EjuoNdZPPdHRCN1dlg0jv8BRsZqUEfSZl2Omje2I39qN7oEDe"
    "g7dOmzQSTnqsYMTeent7OOOqfqVU4crtPcFaqEWbn+/VaeRn3jntSPOHZJQgsdcnUHDVrMdIwNrxBv6dMvBJBuYMlugJDgR2"
    "0WnE2x70X4wZeh566Q8vSVcvAFJnjzdoRfAkzD3ILixDWGBvMUErLMhGV48BV5/tP3IXbXkEoyLHGDuAKmc28Wgh5T+Z90a3"
    "TGdAZbYf+CMPuc3YwdVelTiK9Lhb2dEJvAPmgAxsRTHGFOwoNIpt5rnDIMXW5Ahpdz5QLV0bAb1d+Ndv/vW7H7/7VnRAKCgN"
    "DU2NUGXKSJrK6j/7CtRZToS40f156wHYB9Xqz+RnPTLmf6Ut1S1pfWy1F6YpVdpPTSvVjTV1FA38VaCjFfYBTIo/3kzXtdQ3"
    "NTXIr0AbzvanDGJVflf1VRnu/05QWM3YQoU1/MIqrOFXoRoafGdUVqM5hk9G1L7w61C3tcuSCvXT8DttNtRwZWViCqnbgqt7"
    "OoMw2nC83UDvdltwFdKgN0dLDh+0mq/T6t0Lf/n+T9/8+N33/+wYBfXVjXzuTmkjphFov4BL9/bENZBurWmpa26rE8oodTUN"
    "sF0gikSNTmeMEDw01hjG0UoiuBilHA6mvqnmpyrz86fqe6jBSKE5t8o3sReam5q4NhWhA8AA6xatDuHIADqJGJwh2CrbV3k3"
    "MDbaqs2kwpl7h0+8oy5FGxMnb4SMar3QAyDHgfLyUE9P5k4PopO/FJtL4fy/Kpj/ZwnvFC5BgL2F6KYLx7gIgZCWnXMt+o5M"
    "mOgBUMzMuHc4njBhiuu+F9T0xcJXmY1t947uBdqBne3l87f64qWCuX5VdK/jWxzg/K797UB6Suqc5d0L8DP9848udaerr0em"
    "DIkL81z4MHCWXaWgX9rkp2XIixFKyaMFK/AAPUE3goajotq+yNkH69qSvt7eWBvpJnf6BO9TARITx+2Gep7IYL9/hpIY9DT3"
    "mBhaZkbEwAphCtGw7ArXNXLBLt11+FhVsy6s06WIfjixgOq5/UHtV/VB/VtQKvGAkbwEkTdTRqkY7cN51kdpIq0F/cO52G5P"
    "y8VgEM3VLTXp+hjneEq/wlB3bvkgsrDQy3bWRGZv66pCAaWo3idq7h0vZQd2rdKZgt2gi+CPATgfy+0cOGqbQy41N5vqaoSS"
    "7pRW19Skm3U56quvybCgO85cYisTQH+gDwiEq0abe0jvFp44t5PadE19nWGQtmXveb8/+DCcZ8DO7t61OwTST9dWKVd2iA9g"
    "8fGoMktvaDlCFfvdsFNVUaA5qbJcwG1vq9N/nbFvpSDqoepQ7B9nvPHhxNUpWKGm5nRjdBa5gW2uDywCmB1e9x7gNKzQh6+N"
    "dNEmbuVIu9BQMEq4ybOZWSy+7jysnumL6C2yXO9vHsf35/jij/UR+xs49rb7U7mN50SyJ2fpnwVuqRhWZD+A1vz3Ev7WN6cE"
    "hsgEWjKZY9qiE+v5jgmy9PFORCLwAwgSUCkdKZ1e3wJ8QUTnoO/R99h5drTldRzRzlhcz20v8htxAWXXZrxN6l3oiwBmZpf7"
    "toHF7VcAD2ECsHLy/TuUGvM8hP72Uyjhgn7Pnh3OGcNl5wSmKtv56/f/+m1V3AsOSX5NbMBjWv7AGMGUhDGv+0tvFeqxsFuo"
    "zFDAxxDSo0M0Yd3AYijsAEH0D4wVXWrhdgwcbatzy7gH4bMdfYDvFYdUCNWfWSdmtDeoHgOg+978IUYXwU/bG661QCBVK376"
    "2H9zSg9TT7c3vKfHH19G4YeCWbiOIv/hAx5p2BsdGdAaNtWfhjx7RHIYHvBfG18Cu8q/WLdOEIwc4Inx3cpz9CnCra/I/sFu"
    "7h5NG05qaDE+hbabdQ3XVAJZBzmd+ovg8oqUWUP93B3grAEzLK8rbgeOTAqBPt9HhwjsdfoNRqcsvk3PKBk2EPpgEsaNLdgg"
    "OicvnzrKTs/Be2AsyFeLxjOIxZ18A8EWdYqJvDXYE9U5+M+kFfiMjnc+Yi7042+dgMEKCNAPp5Yi9mwrMx6M/3gHsJiFoEhW"
    "gYOb3aKJ0ReEFeE0GevDVlAUbe7wNIqYym1uYrJRTxk025uBV2+O4NzZPiWuP/YiO76XX30d+J+KnwmXmujvEPcd7Tv48CWY"
    "IfdgG2wyMGMDJyE5HCxnnYXIFTIhIRkMMj8t9qiAXgrgg9d4w30YUdQ3DVXmJxMFYCTh6Ko3yqNAT9SrCTP+EPo8fxfg7gIm"
    "NjKIXSBZQ3GbPdaGzODz41v58ZPELQAMYvqcnsQUGNIB5g0vIGw4iZzJbZ7Ewlva2swxWN71ZnbgJPb2nqmMgpqEL9/PjsKD"
    "DL2qa03PMlHJ8WHau8tbGCHivejt3OjPL5hwAdMh4GnitcFJAA0TbOzrEZ/ICuIGfHjHV4/h5Kd3UGJHFAuL+aZam6sR+WQ9"
    "7+opE57aB2AdXmvZAotbOdagUYmiU8l3jIp37MDbvqe0pFEbPM7DW8FZgBd77SFYbLZ/yTAk6Ur5EFRH0I+Sk6Lsxge03IHH"
    "4M2POmLT1a3wOzTeaKtuTgfeWMAKwwPe5r5wuD1v6zAKTCWdA0tHUFghnTRuyASajI4i8ixY/aMDOGQjzPTIcFJ0qIvurTxB"
    "VB13AgcC5sLGrkJPub0FBCnEAjQaa+vTrW11NT/p+Zoj+jO/6L8lJpLtAjfbikK54eChgGpMWySUq2suOzfDpVdYv2suN7AZ"
    "t9B4UA7XsutviV/LJLjEQN7A8OYXA+/gU64AIhSnGXaBjQFkhHbBqhPCIWhwNVQraMmdPB6lc3ea/AiOVaBUxU6yOwnHbb+f"
    "fT7tPyFH9XemKXclasd/PovAiYAXPZ8Ge3WPM4M1JMxCJTDP9eI7gfkfnZ0ukJYOJxRG8u4NAxOMElJ1ixFsVr8EqO8vSUgH"
    "Nn30qeNBet+JZniGRKvwCEtzHL00R9hxZYodwNENPjU4HMxneZK8HiLR8lZ5gSy14xEjZyZ283M9iJzJvlylN/h4VJUNPIbT"
    "FplMXeNPzdW1Ju4HB4/MdW3c3xLdG38qUSWdCOzHzbqf41QFX5K3tK7eBu/gDQ4Y9Z+TA6gwwOE0goC21eGS1Z9eEfcfXoqJ"
    "a7JVISyQBObD0U/s+sMbamSTsBAkO9iN7cIzBQE39dU1skPcd3Hg+AsnqjnRI7L/7IN4lT3pZLIrtGjhVfG2HyPkAcYZ5JaV"
    "3mg0EB3BE5QvAIdkRvBb+pPLVu5pFIYaLjoc1T6oXapb0s6lurlFBxYEDj+iGrB9j7szt5Nbnn2P9hHRAucRe8h4Lm2LPpd3"
    "e5gIVFOK9Ef3zRT8R9NQLly9VgmTq9h/ImF4A7r+BuV/swjrwEg/69NzjsuNxrrrxt8LJUyDscKYGvgIVtbgT3IcAe9nXvQ/"
    "IdRFXEUaXOcpyXb3W19QqT+66D+5Dw5spYf+zIk87dWYANrX/c9h1FDCd9Ouh+PS75ovEvnZ2HQLIMo1Pf1zL8C6cNyyiFeZ"
    "mzIOpNnd7FhXVDd3YUk7GzdGjqpA3ymDrHpFF3wxDSnN5VnoCI78OOhlGfatPSXoXf0vEgbyIjv4iooU8BGJWiVDlmgXjFCF"
    "YlSYNDVYaQ55C47BWJ7T3KZE5h1PQzBET4g7BQHHZAIXP7V8GC4QxAV39gIMyW2N5DYXNDyEvomlFXC44Hg87KN+G8TOkHUN"
    "9eJL6rT3NmnkYCxDnTTZO7q9LcSevvC6eU64ujLAKG3VtbQYb17HQ0QRglVn4YyYP5LHBw1VhdIkcScuuRPBK3CQ5HZ21E/H"
    "OEecruFNL4hthHK4iwMYMfvQq8gRRhpI96qfMPSxf1h3Ayao0U8gPN++iOnnMPWu3UaceZMJ09WIIpUFD3qzmxuIYcFQHK9+"
    "bDIh3+K2XLSENbHNFScNDJJmgoBIDQ+l/dO9FJpNCCj1B49c209HAX3Rf/iakgE4U0c3zS5sy9grhOKoOwaxTzpMf+5NVNi3"
    "pKtrAUbKpDT6GQbbPq3GPGTRwZswqjD5uIQS86uY+i6B6xxr71Po5DBp8y9nYBxZ82MKzIEi34rIzVGwGjj39NArCM9ZaiTi"
    "1rbyVv8pRORjBsLJOUqIpW6prsMAq9tCrmyiIyQAUoDMdcOOQ8acfH5CBgBPd9AU4D6qWZCA8xoojTCMo2CTYHALaw45mn1N"
    "doJcECQrQ1EHs9fxhKJ0bxCQhUR5RDkBokFqg5BamBNukDUPkIbUJtOcy8rCAwQDl5B/FwPq6eDbh439gqRvvG0SZqts2bGu"
    "XrBvkSD6vmqWjOB+cORNrBiO1rfFxJHpXY2HiIWKNyo7m3kKQs139NBNPfNEcx9UWjg+9NhMmq61plt+rm5rarltpnPJTmeM"
    "Gm9+aRpvmjSHsQdwkGfXMm7cAfmGv9jj6pjgB3jNjsQVOuTjm/fFJ9LrjWR0Wyg9x45Ni3Ze15vqa9O1DdUa6jowo2Zn7rQT"
    "A5AQv2kzn1DfTOYLES6HaHO8SVuWoEw3wxE3J6BLM61HYqaCY3S4D24I+D08RsEQsplJ2qEBr6bmff/U6xkmD8wYfRN9wHyL"
    "0htiv27UG9mDGEdhsyvQ1f03jFvHv/2j0WgsVozmjNIZ2SXwKbxp0LnNCcQDsyE4hHF+DueCLVrqY7yTa5DJa4izyr4GktHN"
    "TdM3J7eoCODLDhkUlLW+qDUGXp2G+6elSU+O6seKZHibB5AMxn89vBdVn98vgEhkoHNkiClX0pDhRcONA7NseI9idGTQ7gs6"
    "o1oG0kA4eO+hsUoRgLaxZWUTvQ6dp4gz8gaex6K+kWcVMAHw9RNsW2d+tof4K6b/bi/3+PC9+sCliODpfQBJIygFY5WBu1Kb"
    "WpDI2/uPQsQRDZODOcJUXWmU/sq+IHIQnzPZfXaw6I2sM8JCwQKAjhMnZI5L05G50NsDd5iaNPNbHlSgU4nVCaKnYB3ztCk/"
    "SFYNIqcmzGS4t5E9YoCy4QMiL6B6wd4J+QBPzNpDl8h0EGRoPbOAG+ll0ZwRCWdCYI5ygARts6Wpqa25qS2ww19PMBQ4c0ol"
    "FsuIXJ+5HidkK1lyRrW0uR5r7wO75+Bgk0F0TW35TyVJbGsihPAUSHVZmiB/JuyHOTIDM/4UPYT+4wWEWsAUQ1gU2Rvw7ZlV"
    "LFHMLKtGCF9NvVIL+NU2ExKhcr/bkoChNSgl0YNv3fYR5SbMORLNkTbYwDo50+KQxo2YlhH1Mc/sB6t5PvEf9EQ2Rp7TzfRH"
    "x6Cq2QQ1KG+K1pukjeHt/OxzwWWQMLkcC3WGA6utmRCrZsi8oPxB1tOxaG8KRT18Gz0+yTMLrZuHb9ENGcDwog2Opr0zvgD6"
    "iuBLEVSj/4X6nwmSvZ4gHLD8mCbB8ThQAEa6vYOHb0BDbcWtOlhgrDW13QTlIBBAdbbOTYBCXjd1LVL23Ik6QrOvjqJYUzCh"
    "iE4Qqmx4A8xQMg7VG2ew9v4HyBqzCWWldD483o1waOnUzATnRKxGNT4pcSaXIIPYOllcxtvujm1NLfz7AfxqhY33Zp8enO0x"
    "GUEnTKtonF0wl1BPuxSeoPFd1bVg6qmi5O+uKyqGz4gKduy1xcf57mE7E+3YG7sPKWETsTTxEtYSZ/hoVIENcmod39w+LKrI"
    "lBC+23SzqaUxAGywuVCcJEVN/SveFLwhr6NKW+GEwq3R5ykX5xeU1GhMwuuDNLRjCzjdH4hxAsZtUWPrYnTkxvNIeIuMht4a"
    "0SUxG40NjDKDn25XX0M4iqgBQMwk/2QSalLumGeWVLZhrVArPYOJFOhrl6wm4K+/8Jc66fcEixvGh35y6N4Dfy2QnVDTQGSu"
    "Capd0aeyMa0KGvW9d51U+ST4FCGEtF5EE5DAlgis3IBhtNRdu6Z8F4gT1/FggVj2kpy0/QWDOIX2QOJ5+dLRAbgLmXHVwv37"
    "T+gApdsG9sleMI8pZGos4LCEonNtWYPpiHqdnBLmP34I6Seeo0O4imALaKwF022WomZNbVNTy0+N9MYrUDP5RsyBl5pBRFh6"
    "ZDOqZzpzCHWySxdDuGldWPIg4x47YXBNqC7AJMrJN6GzKz/R4W6G9qS5xBzEkQkAhjYWAgMBzEG9pr837q+73nTjerVsBn6k"
    "MiRqaF6YF2WWiv4Qa0o4H1bos/kX60awvCYug4BP4ipTsPNOgq3AQzCToXl1rwfozAkzaTCFdxsWaAoibelKovhU/SVR9NfC"
    "cG5orquvN0HvjycZagOBMI4Et5fKwXPHm/g+aju/R2RCY0SXYKREZ0AeolxpSqLk4c4hnitkx9qrZmdZI5pkDUnSxYQsqqUi"
    "SUCebI7e9WfUMAbe5U5OEnAnDKslgGb92RPK7oM3mr5F8GHgJQzcqJlW/Mhfdp1i4CBwCc8dIpKAAQ77XcQrZdPY1OFawMgQ"
    "An/4KoLdSJ8mb12V7u1Jc4pAPCDDfdk9SMtZqErTkvLxHAyyIG0SYSO17fXtDZqD2pOfWEFjgH00jdEbG/AWnkbVteQDFEJR"
    "kuzuv11lmMXWNtpUF3iI2TApbGQzYklLx9wdaDBIUJl/ahM4ma+7QXBdMw44pp5XcSWtpr76dg0CxxprNSjQ+PrmX6qHJj+7"
    "6430RLW0IJI1PpHLlifjLQaH6XYEjlQALUywfTIBMg52Z2mEWebwag8adEP7M94AoT14FjR9UVTgexwWghjUqo7N5Rqg8/+T"
    "TutEDKn3LWggSH7hIYRlruNtVFIWnUuYd93x1suMUwdY2xR5OaxwEfNkNDlBHaeCc8wj7VXDlQyD3tnB+/bg4R2NUEYxEPV/"
    "ewvTWWQJLZwS5BAkKUxVMzYBxtQCe83kQL/1Dgdgm+IsCq6/ApdNVGQ6MwrZ2+WwOgJcPEg+Z/wBIuiJjCOxkrmV7zpD0DaW"
    "ay6oE3tSMvMnDhRIwGjwmuZK0ME2Eggbm3XvCM22NLQYnBrVzZCUwrzCSZQ5mBcyg/e2syBOxJlLATu47CjPfUxQgcuig55V"
    "hGAyEFcdHyvzoVeQqLNkrIZKjcnIgHdjhTUSoH4huH+4C8qzviw5uQsmExXZ2YCnYknJVDmbWqpNuRAFKaEVMudQNbQX64Hl"
    "aY2B5C2y7A0vwh+r4evksCNDUNqZ+NqzR2BCEk5D/ZnoHzBcZPEqP5COKYcE5tf6AoqrI5OBp1sIDfuJIHp/v8C6IWNrq4a7"
    "sy2EcJVUmQ8iNiMINrvREeVs7z9HfEsk2tnRvkYYoTXlNvklZ5e0dZfFEVeTvtUOzWYWsDzkBsPgU+vWCCWvCHLINVUhOrF2"
    "lH5R1sAU9nubCpJrjhgS1RD1FbUKziU+K2DxGpOYmem1A/uS85N8IWLeQXWSUkmFoxOELrTA5Wl4tmSi0KLRrMHRNzBLLc/M"
    "HqE6wCSMoJjN1tTYDMEjAW/Z/ndE2ef7tHQDwD3Ig6hIPXcmVgfVlBrv8T2sirqnrYGtrasDAelgFvk4BXOL7JR0LkrQoGHR"
    "ID6wjicjiG5QTIcEpOVZCkMerte1tLb9VFffqOeFWBYruHS+FB/Zg+zTqagRWpTqQp106rUqBhRqQ73IQPaH+tUUI4fbs5Lo"
    "6BAaY8RGeDplnHOdL41yuv+cUW1B4vHZ4Rva052PNIFK9aJYwYLWtlAvK2V6z8tZye4Qmx2a19gw8pqiSrZNBYkrdZ+HJs/r"
    "ZQYJKKrzeppyRlJ8iIB0r7PUDQM0X0rdj4cAb4M5jo5lx7oj8E4/Nxgaq/rbdESseaDmyLMM9kv8PwL1zj0uCly1NzYgzS5d"
    "W92GOQfZacD4gXmb8MgplojqGYoyQneukQ383M29p34pme8I2aDeubODCTCLCvDcaiiyunMbS+4GojcNZ2fctqh74PI8gMdH"
    "/usVv+uZd/rOeOgPBqHa0LDqeKRoVrSuQN2Nm201TY0I6K0RWhNPn0iu1yeBHb7rrT6I4otFJ/dFCC7gfchKGFzCZ437UfbV"
    "cie4fUM/JAsOQFsNMGByEeSOSi6jRqBmRwZh19sIVF03csaNPqm0Ml+ETJswQIOhhsGHh2soJebNvRb/4SqUyijPdycYyrHP"
    "Q46/BlfoBvMDjk81hJMHZ2CAeD3qOAG4n36uTaPqU8gpqZW4NCq6bI7m8CGVr56wVI6OTsMMDYwysxq3DdMNzW23a1qabjWG"
    "6q1CfQoHilr81Ni6Ic90J1fAND8PgS5Yrj3dVBMktEjlDjm7eKX8x51qaKFdR7XCO47Kq/VGoB1qvREmmh8PM5RHy3OoijLI"
    "lFo+MLvBiB/grTZGqdJUBPsdgqHLappq06kSBtWnSrirt1OootZYW0c2kir5ubq+nT+ka1rSbeVOiPn1ppYS99Wf6hprUyUw"
    "V+ra0AIQ3MRmtH1traSusSQMzK50iix80t4MvpAuu4M9qPi08koJ/3upUvrEx+iLd8vddLfEVy8Xf9XmcNkXNefAgC6xZBd/"
    "+REDq1HcY3E6MaeJv0lA+zIjRpDbrCle/YPIROZeICTICpCimU3xbJ/PC7J9JAGoPv2zBPHzc5DtY7OTXAKMZGUBpppYRwk/"
    "0q0GbsUnIQAbIw1XtonGiHaDkoEMRj5ck2o5mzRPNjMa5kNhjVqAkoHoZDrb+X2WnJgQm+SlwkkyXdJO8nLSJAMeGUmbQeRt"
    "56bmORdJxAKs8hZ14Tqs3aHZ6NnDZ79imp+/N0HtcuEUL186Z4qgzkSqvSIdWcKtIIV/VllZoS9XflLdTJihTA9AORM2lAVo"
    "oUgqAAIwk48i2ouxfp2cq1R1ZOnInSVOVBKyZT2GmVaBSmr7jyjq4V97NyjZtitaOJL5FWEFj9+F+RXXqg1O6EEaz677o/0a"
    "raI5zpFaGFqFQX13SSUYnEIUNJbQzJt+CdXq0xwkJlBmdplOMcZ0Q2qA629jlRiCzHEjodthIav99YhwF8TcqLipBhAr/dKM"
    "TIpIRKqLsNCC+BdgUzOyLJLcL2nwjF4zGf3M4JecqRO4Mqgcd0z6XQP5noe5rc5gcEnFIS5+FnoqW5r+PV1Dyq1r1RoRkiED"
    "Q0wLrGlwHEWH5vBrdQVTUWR/UFULDNoWk4oMl2UINneoDADGQtLB3BsTM846jIOkl7FXJmejWNmQi2EJiBvQBtKNpvbJ40Ge"
    "mf1ngKYkDhE4dGdQOS6oM6B6QVJVARkanB0I2dEoeLqGhroJlgUlEul/CAq0VTglKdx6IEzxbAiokHUphicxU61LAQ8e0o68"
    "oafhsilexdUSnpfdzsRXizVLJtbJzhfXQ40JsQFI+FuZYsLgtJwrVP96NFFYzcBYipVE8EJdqu4apaYBo4GViBCBFxnoDNt6"
    "1hOpz0C1RuzXcG9RDGysR+GcBIJkRj8Acsmj0iWGuUhfAfYZ52dnGtMp3GGDDnFBv7BD/bmuCfl7hhKzYzuIi6LeuYgkxE6T"
    "rUCDIaiQoauqtJK4mAzFsLlG2FDqQrK5jH8/gjr01mAnclJCmgvPB/kryq223dRiUVvcv6F7LIolKiLXb6LTbLKtV6OWE3PH"
    "BN7H0OKkxwCHow6+urzFEGtAcTgnCFhEPK1U/wwGFRphTn2KsJTO9XRLy+0G3Vpqooji7TuABSIxez3+/qKpSGOPrQZeqLmT"
    "cFptCqyJKNvb42L1PkVtPCJrb2ZjtUE4ms/DQOEaVFVqbKtW8xeMihs2yfQ5ls5ETM+81BxiGbJFh+CUsGL7x2o4GsANvVri"
    "SriRp7MIE8r39uZ2XkuAfI+CuLFiMrE1Qq0VQ1KsTSonm4ELrx9qBIM32RPWwAm5Rt+Uss6i7EOL9TAfMKB7sQiGyRwRtdO3"
    "FcYfOBwkWhPGWbtWBPI0NjUY9ibOWbcqlWpU0MGDhUMgulgGCQsnlS0ncNZQXU40C8J2dG8E1gBlhZNAYxmJLe5y6bNIJLvl"
    "cRrvrdgFWHD+Yb8GnkfYnNKGCAWipgknk3zhwb4p1LdyXyzjYcaCaxqWNnk4mVQcS3DYKBuuMenzWtiGpZa2V7IS/QSBH6oB"
    "2F0j90XGQhYmLV2A8Wu1krx4lhU3QgghHEVeb4eWAyysw5QsYJuCigbEegbuKf/J9/YDXjTOjHi1K5hqiEeHh1JaBt34O5mE"
    "s6rphPBXqOOcMeCA7DKsp5KgmXzhjKglGBGwPqgc4EXiyERQlLfyMtxH5T32ICSwMcazMu3bxLPqz6wEiIgapAN2PAERF3Ky"
    "xJpITS03qgPO7x9NoP4jshXEYyzLtDwCtm/2kvSM5JJEtq/UryUhkeJGxzXY6+hbitSp+25cocvwL110UpxaoN2aBWK18dPe"
    "3MY+3mJi0WKP5u8acleWYZepuFQHx9ucJCRKWJ9rxA0W17Ra+0DPgAsVrlQozx1+dotZ1i2KEE6pN0F8J72GkAJdgyeFoyrG"
    "JfyBV6bM7cpzk86KIUndMsLgCKo6PC0saOXwiEtOekVd/a2mBqtiaMVIhi4dv9KoUgBjeUTHq6Jhyo0F+oWRRjHywghVFGrN"
    "SlP1lgy3V5J4FqHWc96imSfoF6GAcg4jtKCmtnajQ9KNNsbsP40+5QnY6oIWG5CZo12ct7sgdopzqaikep/yMyaaIoBKiunF"
    "SC6qql12wObWmzZHJb99lN0c12x5rXYpseATYZE5rIDltVbVKBievg0eMf5MS/kBlFL+ipqgOLu2jKvLaGPVsAJnJuLM4Jw1"
    "y9c1RHbbuQUC1Pxdjg/q+PizUCFy2YjhZ4WUCF7B6D/JPmGg5N5GWPVs4zlhsY1++JtiMjhyUEJG58iF6vr6OlTSbzZrihhJ"
    "eGlg4tHNDs1kyLiDqZzARo9oSpY2E5UTqfIoVweIOUMAEY5tBBz1zKq6grU5V+X90q3nCBzQnOfMLKXXgjpemLSBCt3QzxUb"
    "DE+OFWPJjFlKOGb0YBhniYRUMrx6flA9W1A0g1JkSbUEoxwHKLMpcwyVDpGkYCeIx5hnhoEJRJvuji6fpUrZoWSWSENHyu2C"
    "yyp9U2eSkhqR7NMYYSYVxdS81FBLEUUgN38P6aGYtzgddpFbGoxRTESyj0ALiC+fZIht0nfWuaEZMzAYCPyCWWoRa8TcCRjA"
    "yKbDDavjhRqAo9kJiBSINsmKZAogQoz6Ze0USXLNa3tiilIfDV/xa5PWkEYHB5KE0psbMwZmgFUXnpKQAB3zsBXZyEG4FQWu"
    "KTwtzEtE05BROmP80NQQLVw8eqaOR2DYeONHynCgTuE1ckVEkICxiYXhD54SjkaBmSApw2WP5tRwJf8hQoe1Enwgwx1eonMQ"
    "rkldiYl30JRR/t6UiQ+OyvtMbmoGXUOq0rKMAWx2LO7sQ/9dtwmOnO87z9J2zjKAsRboDnUm7VOjKVae55dY0RRT1pqb3snD"
    "kH/bo5w8PllOyeqGumwLsp/OUHuX6rImxH+/s/Aoh0P8h0horeU13uvnDMkZekBwSuJX/U2UI3oTrp4t/lmU0UD4ofAiBLVx"
    "/W1NwWfJk4LylEJIUfkX+kkdRhMKmOvVwfBYmxTCBZFftux0364ZW0zBsWMrOCQ2MWrixI1gRjoNOKBNpitSrjOUI7Xw6Vqp"
    "nOt7DOHJm2KYGmSSnvBlaJnJrgZjC5TU+LrxhoQFVlCg0o1FOw1vBoAo4QUFITDhDC+EKELufCPd5Ag57iuqPiJG/MExfblM"
    "ncAFCTNR/M5aaInKoWoNhtNLygeZ+ERG7W1WNl7pdsbnmGehcnjZuSwh/RNuyglY83H2cNsYkPNvEDMnCbMZMOuIiLNGeDKE"
    "ghVEGLcocK84wvFdq8EqOaK97MkKjag3ixqpWWiHOzrO51HP6o32wPGIm4IgkZEmuNFnwoIgqYYdI8keEeUNCUuptTypaYbl"
    "lBG5QharHjqcvcLzYVhNVH9FCtY1uMHSJmREygnILpHja+UV9TmrBmv07GCzLccuYDH7Um0DSQhHT8FNWG0UDkkUIltcNTlU"
    "JweFm53IoiWt6hoiRs2Bgf01IjVaoG+9XbTV4yN4QbiEATUmQC0o3W9A+HkJeNs48GfGFYTWah2RKIDYWoZk6egMhPZqkDsF"
    "+NsUFhbZDGyalxOJvc3KiooOqc2ZvMdaMltdpabQK9JyDroVwFUnuJbhVnQI+RwxgRJDXOhUa0MqlDkyNBRX/Z3HuY03jFc5"
    "HNR608kKa1E0VC6nGNT8blOHdAj53LuEKXFvycJSfmnBLWRXBI7/1M1BhdHXEuhcfdiZYbBq9IBpavYZDzY4kdqlRiCLVDrP"
    "6qOOGtTpVuWa+Zdj+/RDdC8Vlup2LL2vnAAC1PgT37gwbbmEINtj6jchWIG7tTPN+tAWfXH5drKpYoq7CzJEXA0JcBLnAJHH"
    "ey0kE87RZhyjOclD1NZ0Wy8Cs2AMRBKC1JGwweTxhTmth86I7ohBqqjkOZyRIgCOpaMVax67MBbCOxHt6ki/0EPkMMQv3SC1"
    "2jrUPrIsnCjVxiKqbzKB+1CKM24sMrzUNe6t3pWMtJEeUa5h5UV+5i0jucfCCDkUbYNj0KDQMAZXnkjp6ieFOliobbvqLIIF"
    "w7HCiQg1EYdFQza4V6PzXs98cKT7T0xKXiKMxAp+PYRomMC40GHuukAuicT0wX2d21lNcBB9EakzA+W/3sqS1SmqMajqLVVm"
    "RB+kDubY8/YcF8XcoECL71SNTc2fwplW/59J/5Q4tYRzbNWbL11u05iuaQ9QSlbgX3rgT/VqVGUU2A0Glww2UJKcyu0jAuya"
    "ZAUcYrkUhAnjQ/P2Ohm9gKRwiCENuviShOqKuy208JgHiHwusaEkT8bcG2gUHWXYxfQbQA6otI2gWqNMgxsyFrqX9UmAWgwO"
    "6yg15zoBH//cTSeg+zQAoRWzV92XA3gwoB5pfIAZn2DDW5lSYMN3PDSWjXBlNWoJbS9NR4oCxLT+UG9wxlh3oxGcJoA1CXIj"
    "yfqQJKR1zNngUU9ks60RWvQEU+h1buplRgw8CeRbWCrcqUvq2qGOmfxVQbnBEN4EKaIYIOUnyn2jKqA49zHGGBYSsOzAgCow"
    "5qWuP+81QokGEOERY9GMfxJZJ8cZrfAILDSBcSeZeVZpCI/2xENzK47qs1sPQFnOUgpNn6duu343wDSqNpH7bY3a5bOpQiEZ"
    "Ondq1NXeqrueNkGqxhMid/txa1F9ZuKJ97zHCYgIpIjlfwkYiNZM5d1owa2HEvW9bC6ECpVCJ8ggZIOO3X67OX0LcVsRr0P/"
    "uCLDjJUDcpaMDBdF3zZHeYK1WJtAb7qnvPJpqF9VbMYqQnd3vIPnO59ZtziUHBTHHbPIoYWOqZWE6SpkmEEmcsuHNVSK0h/U"
    "fp4UEcQMnYM00wA68QHACEp0Eia68lkko8XiNcwRXj2yt8CwaCQl8mESeF3MOAmyrzZM6SKk2+HqswNWish3PUANYtYGC0+G"
    "g1+HmmvoPLne3tJY19bekq5Fcojh1KzoNaXRkyzws0JUBUp1BMUuhIgTQCXE+zLlG5EyUhn5DGGZE+HtF7nukzDCvhg47Fil"
    "wJIQFdV8s6nNtZ4pXOWuQF4udwT0R6vfSDp3xKY6XxLyRIsjkbby+mL27QBYHiNDQKE9dFtrPv4HSj+Gd7U31IV0CbWkfw1Q"
    "neSBjFKzlQjaJGykGP5ApwVsZSVKSCpAw4F9z7CevseKwqIqlsOCkoAIhzpbmqrdA4R6aZPwYu/xSrvpbkSGKVCs9boS3GfW"
    "IEhijhJtASSOeHYQmCzetGEEUZgLW52g3Qjqae0Dx8ZiaDEK6NRXt7QZZJZ4Di51gkAD30BpkntTYCbxhbWmalH004TvoGDJ"
    "+DOUAVSubu6SuPca3pJC89QxpCOxRYjtQOWiUGS/ecucEwTHIe1bvAPe2gNvfSYeSVH0uItHTXxpmkEZeDBAlcCNMWqSgNyC"
    "4b9dcpx/YSKXo1x86VaIuO6GZlHVRu3FxV1lmJroFpGHsQiLJINfYrFshQkNKNTbHn1i8IOxi1SLhFd8oRe5aJVnLFn/gb8x"
    "oGGK5EvmpiBJi908QPHI4ArVlT+4cZg2aJN6jlyjx4qxGxzuhR/+5ds/fffNX6rcK8buBBdNaAqj2UReo8HDC6th7FizBgkq"
    "vZHAppEeb0M2Mp77qFi/off5V9RiJONAS7JorSe2NNLjRJhr0gprREmvmrKiDgKbfKiRd4a4o1mKYvuI5iWlbKAdoy74uz1K"
    "WLgNxffK0JED945JzQmEc7Va4oHLhGDB7iUdD/cYIyNP8ADEOQXARSSLUI85YBw4EInYvtswc9Z7dTI9mtvn9ihIXWv6lllb"
    "rUmlmXJhEh/y69TAj2f7KexlkgNR+3FzwvpY6VOHVaBFVIPemFR3s47QDCPpzGYyfW1/Mwc6CnLrzNyiKXgmUgKGo3hVNDzO"
    "uI3nt0yJNZbh3YqsaBNXM/AdyR0tEpenyWbMe3srqS8bfUhOM/1GU+WUHWnBFK3VGmLgkmjgdtfKhBn01hj0RhgBMclio/NU"
    "HD3TWyWMIHST13TzpC59dmPblndxo0L8gUn06XbIlLGG6lZziY2GWticsezrB8jQMl1FksuMaS6FcjmsvoxB3p7wMggLuKlW"
    "6PbHJC4jnuQ6HKxbkEfI8rLI5ZKkLrOSkbwvNbvV1JYMxgGFm0km/TNmXeeW0IDbIZNYmKLQLgCjkIykW/GGio4jDQdm9lVw"
    "UWIkM4sa+OBpcC/6U1MfN9OnxcTC23iDziTNiXWHGgx5YvtsihNVAlvyR284VHaTkCQ1pQ/YknIIvTE1eoI9ReWwaAU3cxQR"
    "A38tbfmcAObM1EIt241FzUbS+rrgR3LzSTyHSSMBFMGgXzCzrJE3tv6q26XJDmJOjFnahBQh1GhDwUazo7GcIs40yJHRfFZT"
    "hOgxGMdGpA5R0Kek7MDDhyDHmoCjI64MZOukwHD5gnwZ9hNN9lFVVuO+5UMXFtqG47H8SmbEdHlXovNr6pD1UqYpMJoOU4NM"
    "l3JG7BfInk9gYjW0lpVrAD8+N9dDi4BEasS1FYzXd7NUNEOn7nqJxvGXXL0q7WsKTtikCfYvk3HoMK7T9ZBdH1T5+beOoTtB"
    "VxUXK+/+rWNYIud3eWjM1UPDJrE0s1z0+gv8r0ZSeCrCNJ0KDqgSgty2/1llye8IGpSHt7PZhIBSLbER1OUi9CJl/dbBkuA9"
    "MBUw9t8493BAo1k9ojNq9oSBipm3JtV0YZVTsHdgY58EUDMlgCW4rOCGMy3JoTk8dHpCyUdVHdji4ubxxmihmquIgECfvqSv"
    "WaqQMWj3dD7QfeT6NKTpEugJaDC88XZ0ma1IJRiIdAgtTjUM5Yhelibh+FNbtGFfLDBaFaamRjIibzmoGeA/feDrJe+s6xSo"
    "YFrICEFroSk9tuOWoFeXvlZ6J36id3pIDJQzEgOKvJgOwlB2kPrpD47p5W3e0SY9xVrDb2qL9U7BHwRdt3WZpzUJAmpgbuc5"
    "eTDcebjObsOUmkTRL/zkjz40F+YdLbj70g9vPuN6wnSDqQWMQeaxoKVtOSpFwHjRTo+LA5WGV1dLaAFKRpISxofDO0KANnRM"
    "4k5OpFyYYGWn9m30Lj0yBLmsh+FxspPm9uqVblgKyGLVG4ukAkAfsZfoRSmBCg+rTCwUuV/4BT29sy+xgtSLHyESrd+6QXMn"
    "63CD2vEEWWHu1XfsfWCVFRdHOjRdEboltTyhE42VhDKl5WO1nCeQZ7wSDAZFBkV3YXZC91sTjd3fK1XAnps6UigYJiEyQRlh"
    "Q6KCD+rByWa6zg6QXzKg+cGIgpdIG7ngFTcE9L3U+1qJAAwxWAT/thkFpeYKHgZdHajFgEWAmwj/gAtjWbnZwoWMDSEUq9Rg"
    "L97Ta6hiCXr1kKVVvKj2RixLD3Gga3NBImzBdVH9L+mFlFx1k6CD3jVfR26r0nf9zCMyCIl/id0bZa9sov5exZKIerldPE/Q"
    "ZGwLwbojyB2+UQ2fZTkXBmjxSeFTxs7PjWodI17OKTHt1vVc5Noodn+9yl6w56T5BXcmSNTkUnblKHZpll75I9o0n0R4qygP"
    "4XVZ8DuaymNbS/in2O1ZDZA+uJup+lYjcK+EZaDOL6nXsUu0spt7ZMpi1+ozPHVKykejykh1hUjlwlENr4N5d//0/FWphxqJ"
    "4VSxlFD0ijZezAVfkamYp+6DyMhgUyGXAghuNwtp6PPqNCa5zD4SwYOYxw29xcBcM7on2AyQdluTIjKySJafzdCsr60yJUJj"
    "N4+tmsvL5LJl3NgVIR9ZE+b0gDixjVLvnkxBr1gD0R7TiIT9yYplZML9vJYqaCq2jZfdNNJgYAq91XMBa6pb49cZdquOyjx9"
    "2DobscvY+Gtuc09BJK8HEuiRBuJhSvYGMuDdUjCCngIwQcRfiZNym0ToAiJhguuFj7mn7DJPtelCOMvBbsFNZZfFhGisraJK"
    "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"
    "8BI0uw=="
)
_engine = {"__name__": "_night_shop_rules"}
exec(compile(_zlib.decompress(_base64.b64decode(_RULES_B64)).decode("utf-8"),
             "<night-shop-blind-rules>", "exec"), _engine)

_HELP = """口袋夜铺 · 你是独自经营旧物铺的店主。
observe / status：看店况、库存、当前客人和 legal_actions（可做动作）。
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
                   "work_shift", "run_shifts", "choose_event", "unlock_location", "close_for_now", "reopen_shop"}
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
            if action in {"work_shift", "run_shifts", "choose_event", "unlock_location", "close_for_now", "reopen_shop"}:
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
