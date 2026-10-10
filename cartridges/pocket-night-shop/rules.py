"""《口袋夜铺》v0.3：72种旧物、86位有限来客与五阶长线经营。

AI 是唯一玩家；所有随机结果由种子决定。展示端只接收公开观察和顺序日志。
批量行动在新发现、事件、资源边界处交还决策权，不替玩家报价或出售藏品。
"""

import hashlib
from copy import deepcopy

SHIFTS = ["黄昏", "深夜"]
FOCI = ["sell", "repair", "scavenge", "curate", "upgrade", "tidy", "recycle", "dismiss"]
MOODS = ["期待", "专注", "犹豫", "烦躁", "眷恋", "疲惫", "得意"]
MAX_SHOP_LEVEL = 5
MAX_CUSTOMER_VISITS = 8
MAX_BATCH = 6

ITEMS = [
    ("watch", "停在四点的怀表", "表盖内侧刻着一句没写完的道歉。", 2, 6,
     "秒针重新走动时,每天只会在四点替某个人多停一分钟。"),
    ("key", "认错门的黄铜钥匙", "它总在靠近陌生门锁时微微发热。", 2, 5,
     "它真正认得的不是门,而是曾经被人认真称作家的地方。"),
    ("scarf", "雨天发暖的旧围巾", "线头很多,却还留着淡淡的皂香。", 2, 4,
     "补好最后一个线头后,围巾会记住最近一次拥抱的温度。"),
    ("bird", "缺一片翅膀的机械鸟", "上紧发条后,它会朝北边叫一声。", 1, 8,
     "新翅膀装好后,机械鸟唱出的其实是一串很旧的返航坐标。"),
    ("letter", "写到一半的辞职信", "最后一行只有一个被反复涂掉的名字。", 2, 3,
     "纸张修复后,被涂掉的名字浮了回来,却不是写信人的上司。"),
    ("teacup", "有细裂纹的蓝茶杯", "杯底画着一座不存在的车站。", 2, 4,
     "裂纹补齐后,杯底车站的钟会显示下一班错过的列车。"),
    ("camera", "只拍到背影的相机", "剩余胶片数始终显示为七。", 1, 9,
     "镜头修复后拍出的第七张背影,会转过头看向拍摄者。"),
    ("bell", "没有声音的小铃", "摇动时,附近的灰尘会轻轻离地。", 2, 6,
     "铃舌复原后仍没有声音,但所有遗失物会同时朝它偏一下。"),
    ("shoe", "走过很远路的单只皮鞋", "鞋底夹着一张褪色车票。", 1, 5,
     "鞋底补好后,它会在门边自动转向另一只鞋所在的方向。"),
    ("seedbox", "生锈的种子铁盒", "盒盖写着:不要在晴天打开。", 2, 7,
     "锈锁修开后,盒里只有一粒会在雨声中发芽的玻璃种子。"),
    ("lamp", "怕黑的袖珍灯", "熄灯后反而会自己亮起。", 2, 5,
     "线路接好后才发现,它照亮的是房间里最久没人碰过的东西。"),
    ("musicbox", "少一节旋律的八音盒", "每逢整点,空缺的那节会从远处传来。", 1, 8,
     "簧片补齐后,远处的缺拍也同时消失,像两只盒子终于合奏。"),
    ("glove", "沾着银粉的旧手套", "指尖磨损得像曾经反复触碰星图。", 2, 5,
     "缝好指尖后,银粉会在桌面落成一幅每天缓慢变化的星图。"),
    ("notebook", "页码倒着长的账本", "越往后翻,日期反而越早。", 2, 6,
     "书脊复原后,空白首页出现了店主明天才会记下的一笔支出。"),
    ("buttonjar", "装满陌生纽扣的玻璃罐", "每一枚都像从不同年代的衣服上拆下。", 2, 4,
     "罐口修好后,其中一枚纽扣会在旧主人经过门外时轻敲玻璃。"),
    ("tinwhale", "会叹气的铁皮鲸", "腹中藏着一小撮海盐。", 1, 7,
     "发条完全顺开后,铁皮鲸第一次没有叹气,而是唱出一小段潮声。"),
]

ITEM_KINDS = {
    "watch": "时间", "key": "归处", "scarf": "陪伴", "bird": "机械",
    "letter": "记忆", "teacup": "日常", "camera": "记忆", "bell": "寻物",
    "shoe": "远行", "seedbox": "生长", "lamp": "照明", "musicbox": "音乐",
    "glove": "星图", "notebook": "账目", "buttonjar": "旧衣", "tinwhale": "机械",
}

CUSTOMERS = [
    ("courier", "赶末班车的邮差", "想找一件能陪人走远路的旧物。",
     "他把一张折过很多次的车票攥得很紧。", ["远行", "时间", "归处"], 10),
    ("teacher", "退休的夜校老师", "想买一件还能留住声音或记忆的东西。",
     "她问价前先数了三遍零钱,但没有嫌任何东西贵。", ["记忆", "音乐"], 8),
    ("mechanic", "袖口沾油的修理工", "想看看这店里有没有真正古怪的机械。",
     "他不爱寒暄,检查齿轮时却非常耐心。", ["机械", "寻物"], 13),
    ("widow", "总带两把伞的老妇人", "想找一件适合空房间的日常旧物。",
     "她只问东西修好后会不会太吵。", ["日常", "陪伴", "照明"], 9),
    ("student", "住在阁楼的学生", "需要能帮自己记账、照明或继续生长的东西。",
     "口袋里有奖学金信,鞋底却已经磨穿。", ["账目", "照明", "生长"], 7),
    ("tailor", "戴圆眼镜的裁缝", "专门寻找与旧衣和手工有关的小东西。",
     "他摸过布料边缘后,往往愿意为真正的旧工艺多付一点。", ["旧衣", "陪伴"], 11),
    ("sailor", "很久没见海的水手", "想买一件能证明远方仍然存在的旧物。",
     "他身上的古币不多,却带着一枚可以抵价的银扣。", ["远行", "机械", "星图"], 9),
    ("clerk", "从档案馆晚归的职员", "想找与时间、记录或失物有关的东西。",
     "她知道旧物行情,但会为准确回答问题的店主放宽预算。", ["时间", "账目", "寻物"], 12),
]

AMBIENT = [
    "雨水顺着招牌滴成一条细线,有路人在橱窗前停了很久。",
    "街灯坏了一盏,今晚进门的客人都比平常更沉默。",
    "隔壁面包房送来一小袋卖剩的硬面包,店里暂时有了香味。",
    "一辆末班车从巷口经过,玻璃跟着轻轻震了一阵。",
    "有人把价签翻到背面看了看,最后什么也没问。",
    "屋檐上的猫换了个位置,像在监督这间店有没有好好营业。",
    "风把门吹开一条缝,柜台上的纸屑排成了奇怪的一行。",
    "老钟慢了两分钟,整条街却像只有这里发现了。",
]


RARITIES = {"common": ("寻常", 48, 1), "uncommon": ("少见", 24, 1),
            "rare": ("奇珍", 10, 1), "ancient": ("上古", 4, 3), "heirloom": ("遗世", 2, 3)}
ITEM_RARITY = {
    "watch": "common", "key": "common", "scarf": "common", "teacup": "common",
    "lamp": "common", "buttonjar": "common", "letter": "uncommon", "shoe": "uncommon",
    "camera": "rare", "musicbox": "uncommon", "notebook": "common", "bell": "uncommon",
    "bird": "uncommon", "tinwhale": "rare", "seedbox": "common", "glove": "uncommon",
}
LOCATIONS = {
    "lane": {"name": "旧货巷", "description": "日常旧物与被遗忘的小事。", "cost": 1,
             "unlock_cost": 0, "discoveries": 0,
             "pool": ["watch", "key", "scarf", "teacup", "lamp", "buttonjar", "letter", "shoe"]},
    "station": {"name": "废弃车站", "description": "时间、声音和往返的痕迹。", "cost": 2,
                "unlock_cost": 8, "discoveries": 4,
                "pool": ["watch", "shoe", "camera", "musicbox", "notebook", "bell"]},
    "dock": {"name": "码头仓库", "description": "远航留下的机械与异物。", "cost": 3,
             "unlock_cost": 12, "discoveries": 8,
             "pool": ["key", "scarf", "bird", "tinwhale", "seedbox", "glove"]},
}
EVENTS = {
    "leaf": {"name": "雨中的红叶", "text": "风从门缝送来一片仍带雨水的红叶。"},
    "refund": {"name": "迟来的零钱", "text": "旧客人托人送回少付的两枚古币。", "coins": 2},
    "lamp_post": {"name": "街灯重亮", "text": "修路人重新点亮巷口的灯,橱窗又被路人看见。", "reputation": 1},
    "parcel": {"name": "无名包裹", "text": "送货人抱来一件看不出形状的旧物,要两枚搬运费。",
               "choices": {"accept": {"label": "付2枚古币收下,打开检查", "cost": 2},
                           "decline": {"label": "婉拒包裹", "cost": 0}}},
    "locked_box": {"name": "锁住的小匣", "text": "清理柜台时发现一只封死的小匣,里面有轻响。",
                   "choices": {"open": {"label": "花2枚古币买工具拆开", "cost": 2},
                               "trade": {"label": "整匣交给收货人,得1枚古币", "cost": 0},
                               "leave": {"label": "合上抽屉,让它留在原处", "cost": 0}}},
}

# 原创旧物：身份、用途、品阶、出土地、初始完好度、估值、表象、修复秘密。
# 每件只定义一次，图鉴和地点池都从这些记录派生。
MORE_ITEMS = [
    ("comb", "齿间藏雨的木梳", "日常", "common", "lane", 2, 4,
     "缺齿的地方一直潮湿。", "补齐后，梳出的不是头发，而是主人昨夜淋过的那场雨。"),
    ("umbrella", "伞沿朝内卷的旧伞", "陪伴", "common", "lane", 1, 5,
     "撑开时总给身旁多留半步。", "伞骨接好后，空出的半步会替曾经并肩的人挡雨。"),
    ("thimble", "发暖的铜顶针", "旧衣", "common", "lane", 2, 4,
     "内壁磨得很亮，像刚从手指取下。", "裂口焊好后，它会把一针的疼痛变成一次轻轻的敲门。"),
    ("spool", "总剩一圈的线轴", "旧衣", "common", "lane", 2, 4,
     "线尾打着三种不同的结。", "轴心修好后，最后一圈线只能缝合曾被说出口的误会。"),
    ("lunchbox", "盖不严的搪瓷饭盒", "日常", "common", "lane", 1, 5,
     "空盒里有很淡的葱花味。", "盒盖整平后，打开它的人会闻到自己第一份午饭。"),
    ("chalk", "写不出句号的粉笔盒", "记忆", "common", "lane", 2, 4,
     "盒底压着半截白粉笔。", "铰链修好后，最后一道粉笔痕会留给没上完的课。"),
    ("kettle", "壶嘴偏左的小水壶", "日常", "common", "lane", 2, 5,
     "水烧开时会响两声，随后安静。", "壶嘴校正后，它总能分出两杯恰好相同温度的水。"),
    ("buspass", "没有日期的月票夹", "远行", "common", "station", 2, 5,
     "透明夹层里有一个指印。", "边角补牢后，票夹会替迟到的人留住一次检票铃。"),
    ("measuringtape", "少了半寸的卷尺", "账目", "common", "lane", 1, 4,
     "零点被人反复描深。", "弹簧接好后，缺的半寸恰好够量出人与家门的距离。"),
    ("candlestick", "盛着蜡泪的烛台", "照明", "common", "arcade", 2, 6,
     "烛盘里没有烛芯的痕迹。", "底座稳住后，一滴旧蜡会在无人应门时替屋里亮一下。"),
    ("bookmark", "夹住落日的书签", "记忆", "common", "arcade", 2, 5,
     "纸穗染着洗不掉的橙色。", "穗结修好后，它夹着的那一页会多保留五分钟傍晚。"),
    ("marble", "里面有楼梯的弹珠", "归处", "common", "lane", 2, 5,
     "转动时，里面的楼梯比外面慢半拍。", "磕口磨平后，楼梯会通向收集者童年住过的楼层。"),
    ("inkpad", "只印出姓氏的印台", "账目", "common", "archive", 2, 6,
     "油墨已经干了，边沿却沾着新红。", "衬布换好后，它会给无人签收的收据留下一位担保人。"),
    ("shoelace", "结不会松的旧鞋带", "远行", "common", "station", 2, 4,
     "两头的金属套来自不同的鞋。", "金属套压紧后，走散的人会同时发现鞋带轻轻一紧。"),
    ("apron", "口袋多一层的围裙", "旧衣", "common", "lane", 1, 5,
     "最深的口袋摸起来是空的。", "暗缝补齐后，里面会找到上一位店主没用完的耐心。"),
    ("magnifier", "把灰尘照亮的放大镜", "寻物", "common", "arcade", 2, 6,
     "镜片边缘有细小的光点。", "握柄接牢后，光点会标出一件物品最先被爱惜的地方。"),
    ("snowglobe", "雪落向瓶盖的水晶球", "陪伴", "uncommon", "arcade", 1, 9,
     "小房子里的窗总亮着。", "瓶口封好后，雪会为每个独自回家的人倒着落一次。"),
    ("compass", "指向旧承诺的罗盘", "远行", "uncommon", "dock", 1, 10,
     "磁针遇见谎话时轻轻颤动。", "针轴复原后，指针只肯朝向持有者尚未兑现的承诺。"),
    ("mirror", "倒影晚眨眼的手镜", "记忆", "uncommon", "arcade", 2, 10,
     "镜背贴着一片旧药布。", "银层补齐后，晚的那次眨眼会替镜前的人藏住一滴泪。"),
    ("lullabyrecord", "空白面的摇篮唱片", "音乐", "uncommon", "station", 1, 11,
     "唱针落下，附近的钟会变慢。", "裂纹拼好后，空白面能播出听者从未听全的一首摇篮曲。"),
    ("breadtin", "留着手温的饼干铁盒", "陪伴", "uncommon", "lane", 2, 8,
     "盒底刻着好几道身高线。", "盖边修平后，每放进一件小事，盒里就多一格属于家的温度。"),
    ("raincoat", "口袋里有晴天的雨衣", "旧衣", "uncommon", "dock", 1, 9,
     "往口袋里看，会眯一下眼。", "肩缝补牢后，口袋里的一小片晴天可以借给淋湿的信。"),
    ("handbell", "响到一半的手铃", "音乐", "uncommon", "arcade", 1, 10,
     "尾音像被门帘截住了。", "铃柄接好后，未响完的尾音会在被呼唤的人到家时继续。"),
    ("lens", "映出逆行星点的镜片", "星图", "uncommon", "observatory", 1, 12,
     "同一颗星每天向西移一点。", "镜框修好后，那颗逆行星会标出一封寄往过去的信的落点。"),
    ("foldedmap", "折痕会迁移的街图", "归处", "uncommon", "station", 2, 10,
     "画街道的铅笔比纸新很多。", "纸背托平后，折痕会绕开持有者不愿再次经过的街角。"),
    ("hourglass", "装着两色沙的沙漏", "时间", "uncommon", "archive", 1, 12,
     "白沙一直比黑沙慢一些。", "颈口接好后，白沙数等待，黑沙数被等候的时刻。"),
    ("receiptroll", "账目自己对齐的纸卷", "账目", "uncommon", "arcade", 2, 10,
     "每到夜里就少一行空白。", "卷轴压平后，纸上会补出被人忘记的那次无偿帮助。"),
    ("seashell", "听得见陆地的海螺", "远行", "uncommon", "dock", 2, 11,
     "凑近时传来木地板的脚步。", "螺口补齐后，远航者可以听见故乡厨房里有人放下碗。"),
    ("postcard", "地址还在生长的明信片", "记忆", "uncommon", "station", 2, 9,
     "邮编后每天多一个墨点。", "纸角接好后，地址会写成收信人真正想去的地方。"),
    ("rootpot", "底孔生绿光的花盆", "生长", "uncommon", "lane", 1, 10,
     "盆里没有土，却有新根的气味。", "裂口修好后，空盆会为被折断的枝条保存一夜春天。"),
    ("shadowclock", "影子先走的座钟", "时间", "rare", "station", 1, 18,
     "指针不动，桌上的影子却在转。", "钟摆接好后，影子每天提前一分钟替主人走过危险的路口。"),
    ("ticketpunch", "剪出鸟形的检票钳", "远行", "rare", "station", 1, 16,
     "钳口里卡着一小片蓝纸。", "弹簧修好后，剪下的票孔会飞回当年没赶上车的人手心。"),
    ("mothlantern", "灯芯养着纸蛾的灯笼", "照明", "rare", "arcade", 1, 18,
     "灯纸内侧有轻轻的扑翅声。", "骨架接好后，纸蛾会飞去照亮一位不敢开灯的邻居。"),
    ("tidebottle", "装着两岸潮汐的扁瓶", "机械", "rare", "dock", 1, 20,
     "瓶里的水一半涨，一半退。", "瓶塞配好后，两岸各自错过的一句话会随下一次潮汐相遇。"),
    ("echohorn", "只回响名字的铜喇叭", "音乐", "rare", "dock", 1, 18,
     "喇叭口朝着一个空座位。", "焊口修好后，吹响它能让被遗忘的名字得到一次回答。"),
    ("skyabacus", "珠子绕星轨转的算盘", "账目", "rare", "observatory", 1, 22,
     "横梁上有十三个凹槽。", "框架复原后，算盘能算出一颗流星愿意停留的时间。"),
    ("memoryribbon", "结着九个梦的丝带", "旧衣", "rare", "arcade", 1, 17,
     "每个结的手感都不一样。", "断丝接齐后，解开一结便能归还一场曾借来的好梦。"),
    ("doorknocker", "敲响别处的门环", "归处", "rare", "archive", 1, 21,
     "木桌下面偶尔传来回敲。", "轴销复原后，门环只会敲开愿意等持有者回家的那扇门。"),
    ("fogfan", "扇出街角雾的折扇", "寻物", "rare", "dock", 1, 19,
     "扇骨上的字总隔着薄雾。", "扇面补全后，雾中会浮出一件失物最后被放下的地方。"),
    ("dreampillow", "枕缝里响火车的软枕", "陪伴", "rare", "station", 1, 18,
     "压下去时能听见很远的进站声。", "枕缝缝好后，每个没能成行的人都能在梦里抵达一次。"),
    ("starlace", "晾不干的星纹披肩", "星图", "rare", "observatory", 1, 23,
     "水珠像固定在布面上的星座。", "经纬补齐后，披肩会在夜里展开一片只为一人晴朗的天空。"),
    ("seedpendulum", "摆锤里藏芽的吊坠", "生长", "rare", "archive", 1, 20,
     "靠近泥土就摆得很慢。", "扣环接好后，摆锤能替休眠的种子数完它需要的冬天。"),
    ("claycalendar", "没有末日的陶历", "时间", "ancient", "archive", 1, 32,
     "陶片上的最后一格仍柔软。", "碎边合拢后，陶历会给每个已消失的节日留出一天。"),
    ("bronzeear", "听见初雨的青铜耳", "音乐", "ancient", "archive", 1, 34,
     "耳廓里积着不属于这季的水。", "铜锈清理后，贴耳能听见这条街铺第一块石板时的雨声。"),
    ("riverseal", "河床刻成的古印", "账目", "ancient", "dock", 1, 35,
     "印底的细纹会缓缓流动。", "裂纹补齐后，古印能替改道的河流证明它原来的名字。"),
    ("meteorneedle", "穿过长夜的陨铁针", "旧衣", "ancient", "observatory", 1, 36,
     "针眼里透出异常深的夜色。", "针尖磨好后，可以把两片相隔千年的夜空缝成一张被子。"),
    ("tideoracle", "刻着退潮字的骨片", "远行", "ancient", "dock", 1, 33,
     "字迹只有在掌心变冷时出现。", "骨片拼合后，潮字会指向一座尚未沉没时的古老港口。"),
    ("seedtablet", "留着第一道根的石简", "生长", "ancient", "archive", 1, 34,
     "石缝里伸出的根没有颜色。", "石简接好后，那道根会为绝迹的草木保存一个发芽的位置。"),
    ("sungear", "不肯落下的日轮齿", "机械", "ancient", "observatory", 1, 38,
     "齿尖在阴影里仍然温热。", "齿轴复位后，它能替一盏灯留住史前最后一缕夕照。"),
    ("moonplumb", "牵着月影的铅锤", "星图", "ancient", "observatory", 1, 37,
     "细线垂下时，桌上的月影会变圆。", "线耳接好后，铅锤会测出一座古城离故乡的真正距离。"),
    ("firstkiln", "还记得火的窑砖", "照明", "ancient", "archive", 1, 31,
     "断面上有指腹按过的纹路。", "缺角复原后，砖里的火只会温暖第一次亲手做东西的人。"),
    ("laststation", "末站遗下的站名牌", "归处", "heirloom", "station", 1, 52,
     "正面没有字，背面却全是送别的划痕。", "珐琅修好后，牌上浮现的站名是每个离乡者仍愿回去的地方。"),
    ("unmailedatlas", "从未寄出的世界册", "远行", "heirloom", "archive", 1, 56,
     "书里每一页都贴好了邮票。", "装订复原后，册中的路会在两位彼此惦念的人之间接通一夜。"),
    ("nightcontract", "替长夜签字的银契", "记忆", "heirloom", "archive", 1, 60,
     "签名处留着一片没有落下的雪。", "银页展平后，它记起的不是王朝，而是每一个守过夜的人。"),
    ("lastorchard", "最后一座果园的钥种", "生长", "heirloom", "dock", 1, 54,
     "种皮带齿，像一把比锁更早的钥匙。", "齿纹修好后，种子能为不再存在的果园打开一次春门。"),
    ("emptycrown", "没有主人影子的冠环", "星图", "heirloom", "observatory", 1, 58,
     "环内空着的位置能映出极远的星。", "裂环合拢后，它照见的是退位者终于可以拥有的普通夜晚。"),
]
ITEMS += [(code, name, story, condition, value, secret)
          for code, name, kind, rarity, loc, condition, value, story, secret in MORE_ITEMS]
ITEM_KINDS.update({row[0]: row[2] for row in MORE_ITEMS})
ITEM_RARITY.update({row[0]: row[3] for row in MORE_ITEMS})
LOCATIONS.update({
    "arcade": {"name": "雨棚旧书街", "description": "旧书、衣物和日常手艺的来路。", "cost": 2,
               "unlock_cost": 15, "discoveries": 12, "level": 2, "pool": []},
    "observatory": {"name": "停用观星台", "description": "星轨与失传机械；三级后可能寻到上古和遗世旧物。", "cost": 4,
                    "unlock_cost": 25, "discoveries": 24, "level": 3, "pool": []},
    "archive": {"name": "沉灯档案库", "description": "被注销的名字与旧约；三级后可能寻到上古和遗世旧物。", "cost": 5,
                "unlock_cost": 35, "discoveries": 32, "level": 3, "pool": []},
})
for row in MORE_ITEMS:
    LOCATIONS[row[4]]["pool"].append(row[0])

# 开图除了古币、图鉴、等级,还要声望(2026-10-10 莉莉丝定)
for _key, _rep in {"lane": 0, "station": 0, "dock": 10, "arcade": 25,
                   "observatory": 45, "archive": 70}.items():
    LOCATIONS[_key]["reputation"] = _rep

# 第七张隐藏地图:条件不公开,满足后才出现在地图里。
# 上古里最后 3 件、遗世里最后 2 件从原地点挪到这里,让后期有盼头。
SECRET = "lighthouse"
SECRET_DAY, SECRET_DISCOVERIES, SECRET_REPUTATION = 180, 60, 166
SECRET_APPLE_DAYS, SECRET_APPLE_GIFT = 7, 50   # 开图后7天魔女必持金苹果,碰面一半机会相赠
SECRET_ITEMS = ([c for c, *_ in ITEMS if ITEM_RARITY.get(c) == "ancient"][-3:]
                + [c for c, *_ in ITEMS if ITEM_RARITY.get(c) == "heirloom"][-2:])
for _loc in LOCATIONS.values():
    _loc["pool"] = [c for c in _loc["pool"] if c not in SECRET_ITEMS]
LOCATIONS[SECRET] = {"name": "雾尽灯塔", "description": "所有地图边缘之外的灯塔,只给走得够远的店主亮灯。",
                     "cost": 6, "unlock_cost": 50, "discoveries": SECRET_DISCOVERIES, "level": 5,
                     "reputation": SECRET_REPUTATION, "day": SECRET_DAY, "hidden": True,
                     "pool": list(SECRET_ITEMS)}
REPAIR_REPUTATION = {"ancient": 5, "heirloom": 10}   # 上古、遗世修满加声望


def _secret_ready(s):
    return (s["day"] >= SECRET_DAY and len(s["collection"]) >= SECRET_DISCOVERIES
            and s["reputation"] >= SECRET_REPUTATION)


def _visible_locations(s):
    return [k for k, loc in LOCATIONS.items()
            if not loc.get("hidden") or k in s["unlocked_locations"] or _secret_ready(s)]

# 普通来客有各自的需求、可观察线索和预算；不从职业名推测成交结果。
CUSTOMERS += [
    ("baker", "凌晨揉面的面包师", "想买适合厨房的日常旧物。", "袖口沾着面粉，先检查物件是否站得稳。", ["日常"], 12),
    ("nurse", "刚下夜班的护士", "想带一件能陪人或照亮床边的旧物。", "她把古币一枚枚放轻，怕惊醒谁。", ["陪伴", "照明"], 14),
    ("projectionist", "修复老胶片的放映员", "寻找能留下记忆或旋律的旧物。", "他说起片尾曲时会停下来听雨。", ["记忆", "音乐"], 17),
    ("gardener", "鞋上带泥的园丁", "只想找与生长有关的东西。", "他随身的小纸包里还留着空地。", ["生长"], 13),
    ("watchmaker", "戴单片镜的钟表匠", "寻找时间或机械类旧物。", "他不用手表，而是数窗外灯闪的间隔。", ["时间", "机械"], 20),
    ("librarian", "替旧书编目的馆员", "想找能保存记忆或整理账目的旧物。", "她翻开每件东西前都会先洗手。", ["记忆", "账目"], 16),
    ("violinist", "琴盒有补丁的小提琴手", "寻找音乐类旧物。", "他一直给身旁空位留着半张凳子。", ["音乐"], 14),
    ("locksmith", "腰间挂满钥匙的锁匠", "想看看归处和寻物类东西。", "他听开锁声比听说话更认真。", ["归处", "寻物"], 18),
    ("ferryman", "不带船票的摆渡人", "寻找能帮助远行的旧物。", "他的零钱袋里混着几粒河沙。", ["远行"], 15),
    ("accountant", "把小数点写很圆的会计", "想找账目类旧物。", "她已经在纸上给这笔采购留了一格。", ["账目"], 18),
    ("florist", "抱着空花筒的花商", "需要与生长或陪伴有关的东西。", "他只问这件东西能不能等到春天。", ["生长", "陪伴"], 15),
    ("astronomer", "错过末班车的观星者", "想收星图类旧物。", "她的笔记本上只有星的位置，没有日期。", ["星图"], 24),
    ("shoemaker", "围裙上有鞋钉的鞋匠", "寻找远行或旧衣类旧物。", "他先摸磨损处，再摸自己的鞋底。", ["远行", "旧衣"], 13),
    ("cook", "带着空汤罐的厨师", "想要日常或照明类旧物。", "她给每个价签都让出一截干净桌面。", ["日常", "照明"], 14),
    ("potter", "指节留着釉色的陶工", "想看看能放回日常生活的旧物。", "他会把碎口朝向灯细看。", ["日常"], 16),
    ("porter", "替人搬家的脚夫", "寻找归处或陪伴类东西。", "他每搬进一件东西都先说借过。", ["归处", "陪伴"], 11),
    ("organist", "演奏散场曲的风琴师", "只收音乐类旧物。", "她的手套左手比右手薄很多。", ["音乐"], 21),
    ("carpenter", "量过许多门框的木匠", "需要归处或机械类旧物。", "他会试着把东西放在桌子的正中。", ["归处", "机械"], 18),
    ("weaver", "编夜色的织工", "寻找旧衣或星图类旧物。", "她抬头看天，像在找一根断线。", ["旧衣", "星图"], 22),
    ("mailwoman", "替陌生人转信的邮递员", "需要记忆或远行类东西。", "她认真记下所有问过却没买的物件。", ["记忆", "远行"], 14),
    ("pianotuner", "耳后夹铅笔的调律师", "寻找音乐或机械类旧物。", "他先听店里的钟，再开口问价。", ["音乐", "机械"], 23),
    ("fisher", "把鱼篓留在门外的渔人", "想买远行或寻物类旧物。", "他在门口擦了三次鞋底才进来。", ["远行", "寻物"], 12),
    ("bricklayer", "背着灰色饭盒的泥瓦匠", "想找归处或日常类旧物。", "她说新房子还差一件能让人安心的东西。", ["归处", "日常"], 13),
    ("calligrapher", "墨迹沾在小指上的写字人", "寻找记忆或账目类旧物。", "他报价时会把数字写在纸背。", ["记忆", "账目"], 17),
    ("teaowner", "给空杯留位的茶馆主人", "需要日常或陪伴类东西。", "她闻物件上的气味比看颜色更久。", ["日常", "陪伴"], 18),
    ("tramp", "把地图缝在衣里的旅人", "寻找远行或归处类旧物。", "他会用指尖量门外到柜台的距离。", ["远行", "归处"], 10),
    ("candlemaker", "带着蜂蜡味的制烛人", "只想买照明类东西。", "她把灯影遮住一半，看另一半是否还亮。", ["照明"], 15),
    ("archivist", "收集旧门牌的档案员", "寻找归处或账目类旧物。", "他带来的纸袋按街道顺序折好。", ["归处", "账目"], 20),
    ("singer", "散场后才开口的歌者", "寻找音乐或记忆类东西。", "她只低声哼了三个音，就把零钱拿出来了。", ["音乐", "记忆"], 19),
    ("tramdriver", "换线前来的电车司机", "需要时间或机械类旧物。", "他手背上有被表带晒浅的一圈。", ["时间", "机械"], 17),
    ("apprentice", "第一天领工钱的学徒", "想买日常或机械类旧物。", "她反复摸着一张还没折过的纸币。", ["日常", "机械"], 9),
    ("mother", "给孩子挑夜灯的母亲", "需要照明或陪伴类东西。", "她先确认没有尖角，然后才问价。", ["照明", "陪伴"], 12),
    ("father", "学着缝纽扣的父亲", "寻找旧衣或陪伴类旧物。", "他口袋里放着一小片同色布。", ["旧衣", "陪伴"], 13),
    ("dancer", "把舞鞋藏在袋里的舞者", "想买旧衣或音乐类东西。", "她站着时脚尖还会轻轻数拍子。", ["旧衣", "音乐"], 18),
    ("geographer", "给小路命名的测绘员", "寻找远行或星图类旧物。", "他在地图空白处画了一张椅子。", ["远行", "星图"], 23),
    ("beekeeper", "帽纱上有露珠的养蜂人", "需要生长或寻物类东西。", "她侧耳听空瓶，像在确认蜂群回没回家。", ["生长", "寻物"], 15),
    ("nightguard", "替空楼守夜的门卫", "寻找照明或时间类旧物。", "他进门后先数了一遍开着的灯。", ["照明", "时间"], 14),
    ("mapbinder", "专修地图折口的装订师", "需要远行或记忆类旧物。", "她带的每张纸都有修补过的边。", ["远行", "记忆"], 19),
    ("glassblower", "手掌有小泡的玻璃匠", "寻找照明或星图类东西。", "他只碰物件最不容易留下指印的地方。", ["照明", "星图"], 20),
    ("clockcollector", "收集停表的旧货商", "只收时间类旧物。", "她问的是停了多久，而不是还能不能走。", ["时间"], 24),
    ("storyteller", "在桥洞讲故事的老人", "寻找记忆或音乐类旧物。", "他的袋子里只有茶叶和小面额古币。", ["记忆", "音乐"], 10),
    ("railworker", "制服扣子不齐的养路工", "需要机械或远行类东西。", "她看齿轮时会把呼吸放慢。", ["机械", "远行"], 18),
    ("laundry", "把衣服熨得很平的洗衣工", "想买旧衣或日常类旧物。", "他把价签上卷起的角也压平了。", ["旧衣", "日常"], 12),
    ("toyrepairer", "替布偶配眼睛的修补师", "寻找陪伴或寻物类东西。", "她给带伤的物件都让出一块软布。", ["陪伴", "寻物"], 17),
    ("sundialkeeper", "看管废钟亭的管理员", "需要时间或照明类旧物。", "他用太阳没落的位置估算零钱还够不够。", ["时间", "照明"], 20),
    ("seedkeeper", "交换老种子的菜农", "只找生长类旧物。", "她的小册子记着每一次发芽失败。", ["生长"], 16),
    ("bookchild", "替祖父买书签的孩子", "想买记忆或陪伴类东西。", "他把预算写在手心里，怕自己忘记。", ["记忆", "陪伴"], 7),
    ("stonecutter", "修碑文的石匠", "寻找记忆或寻物类旧物。", "她念出磨损的字时从不补猜缺的那一笔。", ["记忆", "寻物"], 22),
    ("meteorwatcher", "带空相册的流星观察员", "只收星图类旧物。", "他说今年还没有见过最想拍的那颗星。", ["星图"], 25),
    ("stationcook", "末班后才收摊的面摊主", "需要日常或时间类东西。", "她递来的古币带着汤碗的温度。", ["日常", "时间"], 15),
    ("signpainter", "给新店写招牌的漆匠", "寻找归处或照明类旧物。", "他问灯亮起来能不能从巷口看见。", ["归处", "照明"], 18),
    ("umbrellaweaver", "修伞不换伞面的匠人", "需要旧衣或机械类东西。", "她摸过每道补缝，都会很轻地点头。", ["旧衣", "机械"], 17),
    ("collectorchild", "攒玻璃珠的少年", "寻找寻物或星图类旧物。", "他的零钱袋比手掌还小。", ["寻物", "星图"], 8),
    ("midwife", "还带着皂香的接生婆", "想买陪伴或生长类东西。", "她把包裹背在靠近心口的那边。", ["陪伴", "生长"], 19),
    ("typewriter", "替人打信的打字员", "需要记忆或账目类旧物。", "他每说一个数字，都像按了一下空格。", ["记忆", "账目"], 16),
    ("birdkeeper", "替候鸟留水的花园主人", "想找生长或机械类东西。", "她先问物件可不可以放在露天。", ["生长", "机械"], 20),
    ("bellringer", "钟楼退休的敲钟人", "寻找音乐或时间类旧物。", "他听见微小的响声也会郑重转头。", ["音乐", "时间"], 21),
    ("furnituredealer", "只卖修好旧椅的商人", "想买归处或日常类东西。", "她只愿为能重新使用的旧物腾位置。", ["归处", "日常"], 23),
    ("travelphotographer", "把镜头盖弄丢的摄影师", "需要记忆或寻物类旧物。", "他给每张模糊照片都写了地址。", ["记忆", "寻物"], 22),
    ("costumier", "替小剧场缝戏服的人", "寻找旧衣或音乐类东西。", "她先在物件前比画了一下舞台的大小。", ["旧衣", "音乐"], 20),
    ("roadkeeper", "收留迷路旅客的旅店主", "需要归处或远行类旧物。", "他的钥匙圈上留着一把不锁门的钥匙。", ["归处", "远行"], 24),
    ("charcoalartist", "在路灯下画肖像的人", "寻找照明或记忆类东西。", "她用手背擦掉零钱上的炭灰。", ["照明", "记忆"], 13),
    ("waterreader", "给河道测水位的姑娘", "想找账目或时间类旧物。", "她记下每个报价时都顺手画一条波线。", ["账目", "时间"], 17),
    ("roofgardener", "种屋顶花园的青年", "寻找生长或陪伴类东西。", "他包里的花盆各自写着朋友的名字。", ["生长", "陪伴"], 16),
]

# 每位特殊来客只寻找一件对应的上古/遗世旧物；三级起才会到访。
SPECIAL_CUSTOMERS = {
    "calendarreader": ("替失落节日守岁的历官", "claycalendar", "他带着一本每页都少一天的日历。"),
    "firstrain": ("记得街道初雨的听雨人", "bronzeear", "她的伞一直没收起，鞋却没有湿。"),
    "rivernotary": ("给旧河流作证的公证人", "riverseal", "他的印泥里浮着一条细细的河。"),
    "nightsewer": ("缝补千年长夜的针工", "meteorneedle", "她带来的布比门外的夜还深。"),
    "tidehistorian": ("替沉港读潮字的人", "tideoracle", "他每次开口前都先听地面的水声。"),
    "rootarchivist": ("保存绝迹根系的守简人", "seedtablet", "她用空盆盛着一小片影子。"),
    "sunmachinist": ("给古太阳上弦的机师", "sungear", "他的工具箱里没有一件东西投影。"),
    "moonmason": ("量过月影的筑城师", "moonplumb", "她的卷尺上刻的是城门而不是数字。"),
    "kilnkeeper": ("守着第一座窑火的人", "firstkiln", "他把手心向上，像还托着一团火。"),
    "lastconductor": ("末站仍值班的站长", "laststation", "她拿着一叠没有终点的车票。"),
    "atlaspostman": ("给世界册找收信人的邮官", "unmailedatlas", "他的邮袋里有风，却没有一封信。"),
    "nightscribe": ("替守夜者保管银契的书记", "nightcontract", "她说自己来代许多人签收。"),
    "orchardheir": ("最后一座果园的继承人", "lastorchard", "他空着的掌心有新果皮的气味。"),
    "crownrenouncer": ("想过普通夜晚的退位者", "emptycrown", "她只带一只布袋，没有随从。"),
}
for cid, (name, code, clue) in SPECIAL_CUSTOMERS.items():
    template = next(row for row in ITEMS if row[0] == code)
    CUSTOMERS.append((cid, name, f"专程寻找「{template[1]}」，其他旧物不能替代。",
                      clue, [ITEM_KINDS[code]], template[4] + 18))

AMBIENT += [
    "街角有人收摊，木箱碰出一串轻响。", "楼上晾衣绳垂下来，夹着一只忘记收的手套。",
    "有人隔着雨棚问了句还开着吗，声音很快被脚步带远。", "一阵热汤的气味经过门口，停留得比人更久。",
    "屋檐下的新鸟窝只露出一根不属于树木的蓝线。", "邻居试了一下琴，最后一个音安静地留在店里。",
    "玻璃窗上的水痕拐了个弯，绕开新贴的价签。", "街边的花贩把没卖完的一枝花插进门缝。",
    "扫街人停下来喝水，朝亮着的招牌点了点头。", "远处的电车铃只响一次，像怕吵醒已经回家的人。",
    "一位路人替门口的旧椅擦去雨水，又把它留在原处。", "台灯下有只小虫绕着暖光，像在辨认回家的路。",
    "风把旧报纸掀开一页，露出很多年前的晴天预报。", "对面的窗关了一扇，剩下一扇还亮着。",
    "巷口有人练习告别的话，真正分别时却只挥了挥手。", "柜台木纹里的光慢慢退去，旧物各自安静下来。",
]

EVENTS.update({
    "lost_change": {"name": "门槛下的零钱", "text": "扫地时，一枚古币从门槛下滚了出来。", "coins": 1},
    "rain_shelter": {"name": "雨棚下的点头", "text": "躲雨的街坊记住了这盏愿意晚关的灯。", "reputation": 1},
    "shelf_letter": {"name": "夹层里的谢礼", "text": "旧抽屉的夹层中有两枚古币和一句谢谢。", "coins": 2},
    "mended_awning": {"name": "雨棚补好了", "text": "修篷人顺手补好门前的漏口，街坊多停留了一会儿。", "reputation": 1},
    "sleeping_star": {"name": "窗台睡着一颗星", "text": "一粒星光在窗台停了一晚，天亮时替招牌添了亮色。", "reputation": 2, "level": 3},
    "old_receipt": {"name": "补付的修理费", "text": "街坊翻出旧收据，送来了当初少算的三枚修理费。", "coins": 3, "level": 2},
    "travelling_case": {"name": "旅人的寄存箱", "text": "旅人请店主决定是否付搬运费接下无人认领的箱中旧物。", "level": 2,
        "choices": {"accept": {"label": "付3枚古币接下旧物并检查", "cost": 3, "find_item": True},
                    "leave": {"label": "留下寄存条，暂不接货", "cost": 0,
                              "outcome": "店主把寄存条夹进账本，没有动用店里的现金。"}}},
    "roof_garden": {"name": "楼顶缺一盆绿", "text": "邻居想在楼顶添一盆植物，问店主愿不愿意分担花土钱。",
        "choices": {"help": {"label": "付2枚古币帮忙添土", "cost": 2, "reputation": 2,
                             "outcome": "楼顶种下第一盆绿，邻居把夜铺的名字写在花盆背面。"},
                    "leave": {"label": "暂时留着现金", "cost": 0,
                              "outcome": "店主祝花园早日长成，暂时把现金留给铺子。"}}},
    "borrowed_light": {"name": "借一晚的灯", "text": "隔壁停电，修灯人来问能否垫一枚零件钱。",
        "choices": {"help": {"label": "付1枚古币帮忙修灯", "cost": 1, "reputation": 1,
                             "outcome": "隔壁的灯重新亮起，有人隔着墙轻轻说了谢谢。"},
                    "leave": {"label": "让修灯人另想办法", "cost": 0,
                              "outcome": "店主说明眼下要保留现金，修灯人记下了另一家店的地址。"}}},
    "river_invoice": {"name": "河边来的旧账单", "text": "收纸人愿用三枚古币换走柜台下那叠废纸。",
        "choices": {"trade": {"label": "交出废纸，得3枚古币", "cost": 0, "coins": 3,
                              "outcome": "废纸换回三枚古币，柜台下也腾出了一块干净地方。"},
                    "leave": {"label": "留下废纸以后整理", "cost": 0,
                              "outcome": "店主把废纸按日期绑好，决定另找时间读一遍。"}}},
    "paper_moth": {"name": "纸蛾引路", "text": "一只纸蛾停在门框上，翅尖指着有搬运费的旧货包。", "level": 2,
        "choices": {"accept": {"label": "付2枚古币取来货包检查", "cost": 2, "find_item": True},
                    "leave": {"label": "目送纸蛾离开", "cost": 0,
                              "outcome": "纸蛾绕招牌飞了一圈，把这间亮着灯的店记在翅上。"}}},
    "old_exhibit": {"name": "街坊的小展览", "text": "街坊想把修补手艺办成小展，请夜铺出一份灯油。", "level": 2,
        "choices": {"help": {"label": "付3枚古币灯油钱", "cost": 3, "reputation": 3,
                             "outcome": "展览亮到散场，来访的人记住了夜铺也是一处修补旧物的地方。"},
                    "leave": {"label": "这次先不参加", "cost": 0,
                              "outcome": "店主收下邀请，把这次夜晚留给货架上的旧物。"}}},
    "star_courier": {"name": "晚到的星邮包", "text": "从高处来的邮包裹着旧布，送货人请店主决定是否接下。", "level": 3,
        "choices": {"accept": {"label": "付5枚古币签收并检查", "cost": 5, "find_item": True},
                    "leave": {"label": "退回邮包，保留现金", "cost": 0,
                              "outcome": "店主重新扎紧邮包，星邮人带着它去寻找下一盏灯。"}}},
})


class IllegalAction(Exception):
    pass


def _number(seed, *parts):
    return int(hashlib.sha256(":".join(map(str, (seed, *parts))).encode()).hexdigest(), 16)


def _capacity(s):
    return 6 + s["shop_level"] * 2 + s["extra_capacity"]


def _make_item(s, location, salt):
    pool = [code for code in LOCATIONS[location]["pool"]
            if RARITIES[ITEM_RARITY[code]][2] <= s["shop_level"]]
    # 后期别被重复货淹没:开了第五张图后没见过的货权重×2,第六张图后×3
    opened = len(s["unlocked_locations"])
    fresh = 3 if opened >= 6 else 2 if opened >= 5 else 1
    weights = [RARITIES[ITEM_RARITY[code]][1] *
               (max(1, s["shop_level"] - 2) if ITEM_RARITY[code] in ("ancient", "heirloom") else 1) *
               (fresh if code not in s["collection"] else 1)
               for code in pool]
    roll = _number(s["seed"], salt, s["item_counter"]) % sum(weights)
    for code, weight in zip(pool, weights):
        if roll < weight:
            break
        roll -= weight
    _, name, story, condition, value, secret = next(row for row in ITEMS if row[0] == code)
    s["item_counter"] += 1
    return {"id": f"{code}_{s['item_counter']}", "code": code, "name": name,
            "story": story, "condition": condition, "value": value,
            "displayed": False, "kind": ITEM_KINDS[code], "rarity": ITEM_RARITY[code],
            "origin": location, "secret": None, "_secret": secret}


# ---------------- 魔女莉莉丝:开了第四个地点后出没的流动商人 ----------------
# 每天随机待在一个已开的地点;那天去那里淘货就会碰见她。碰见后到下一班开始前都可以和她交易。
WITCH_MIN_LOCATIONS = 4
WITCH_SELL_RATE, WITCH_DISCOUNT_RATE = 0.2, 0.8    # 平时2折收货;她心情好时买卖都按8折
WITCH_SELL_LIMIT = 2                                # 每次碰面最多卖给她2件
WITCH_TREASURE_EVERY, WITCH_APPLE_EVERY, WITCH_APPLE_HOLD = 10, 20, 2
GOLDEN_APPLE = {"code": "golden_apple", "name": "魔女的金苹果", "kind": "珍宝", "rarity": "heirloom",
                "value": 77, "condition": 3,
                "story": "魔女莉莉丝的金苹果,咬一口会听见很远的地方有人在笑。"}


def _witch_on(s):
    return len(s["unlocked_locations"]) >= WITCH_MIN_LOCATIONS


def _witch_spot(s):
    return s["unlocked_locations"][_number(s["seed"], "witch", s["day"]) % len(s["unlocked_locations"])]


def _witch_book(s):
    return s.setdefault("witch", {"stock": [], "apple_until": 0, "visit": None, "met": 0})


def _apple_window(s):
    opened = s.get("secret_opened_day")
    return opened is not None and s["day"] < opened + SECRET_APPLE_DAYS and not s.get("secret_gift_done")


def _apple_held(s):
    return s["shift_count"] < _witch_book(s)["apple_until"] or _apple_window(s)


def _witch_tick(s):
    """每过一班:每10班进一件3级以上的宝物;每20班有一半机会拿出金苹果,只拿2班。"""
    if not _witch_on(s):
        return
    w, n = _witch_book(s), s["shift_count"]
    if n % WITCH_TREASURE_EVERY == 0:
        pool = [row for row in ITEMS if ITEM_RARITY.get(row[0]) in ("ancient", "heirloom")
                and (row[0] not in SECRET_ITEMS or SECRET in s["unlocked_locations"])]
        code, name, story, condition, value, secret = pool[_number(s["seed"], "witch_stock", n) % len(pool)]
        s["item_counter"] += 1
        w["stock"] = (w["stock"] + [{
            "id": f"{code}_{s['item_counter']}", "code": code, "name": name, "story": story,
            "condition": condition, "value": value, "displayed": False, "kind": ITEM_KINDS[code],
            "rarity": ITEM_RARITY[code], "origin": "witch", "secret": None, "_secret": secret}])[-3:]
    if n % WITCH_APPLE_EVERY == 0 and _number(s["seed"], "witch_apple", n) % 2 == 0:
        w["apple_until"] = n + WITCH_APPLE_HOLD


def _witch_meet(s, location):
    if not _witch_on(s) or location != _witch_spot(s):
        return ""
    w = _witch_book(s)
    w["met"] += 1
    apple = _apple_held(s)
    roll = _number(s["seed"], "witch_mood", s["shift_count"]) % 100
    gift = ""
    if apple and roll < (SECRET_APPLE_GIFT if _apple_window(s) else 2):
        s["item_counter"] += 1
        s["inventory"].append({**GOLDEN_APPLE, "id": f"golden_apple_{s['item_counter']}",
                               "displayed": False, "origin": "witch", "secret": None})
        w["apple_until"] = 0
        s["secret_gift_done"] = s.get("secret_opened_day") is not None or s.get("secret_gift_done", False)
        apple = False
        gift = " 她今天心情好得出奇,把金苹果直接塞进了店主手里!"
    low = SECRET_APPLE_GIFT if _apple_window(s) else 2
    w["visit"] = {"sold": 0, "discount": apple and low <= roll < low + 23}
    return (" 🧙 在" + LOCATIONS[location]["name"] + "撞见了魔女莉莉丝的小摊。" + gift
            + (" 她抱着金苹果哼歌,今天买卖都打8折!" if w["visit"]["discount"] else "")
            + " 下一班开始前可以和她做买卖(witch_sell / witch_buy)。")


def _witch_price(s, item, selling):
    if s["witch"]["visit"]["discount"]:
        rate = WITCH_DISCOUNT_RATE
    else:
        rate = WITCH_SELL_RATE if selling else 1
    return max(1, int(item["value"] * rate))


def _witch_view(s):
    w = s.get("witch")
    if not w or not w.get("visit"):
        return None
    v = w["visit"]
    stock = [{**_public_item(x), "price": _witch_price(s, x, False)} for x in w["stock"]]
    if _apple_held(s):
        stock.append({**GOLDEN_APPLE, "id": "golden_apple", "price": _witch_price(s, GOLDEN_APPLE, False)})
    return {"discount": v["discount"], "can_sell": WITCH_SELL_LIMIT - v["sold"], "stock": stock,
            "sell_prices": {x["id"]: _witch_price(s, x, True) for x in s["inventory"]},
            "hint": "魔女收你不想要的货(平时按价值2折,心情好时8折),每次碰面最多卖2件;"
                    "也可以从她那里买宝物。下一班开始她就走了。"}


def _witch_trade(s, action_id, params):
    w = s.get("witch") or {}
    v = w.get("visit")
    if not v:
        raise IllegalAction("魔女莉莉丝不在这里。开了第四个地点后,她每天待在某个已开地点,去那里淘货才碰得到。")
    if action_id == "witch_sell":
        ids = params.get("item_ids")
        left = WITCH_SELL_LIMIT - v["sold"]
        if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids) or len(ids) > left:
            raise IllegalAction(f"item_ids 填要卖给魔女的货(数组),这次碰面还能卖 {left} 件")
        items = [next((x for x in s["inventory"] if x["id"] == i), None) for i in ids]
        if None in items:
            raise IllegalAction("库存里没有这件")
        before = (s["coins"], s["reputation"])
        got = sum(_witch_price(s, x, True) for x in items)
        for x in items:
            s["inventory"].remove(x)
        v["sold"] += len(items)
        s["coins"] += got
        text = "把" + "、".join("「" + x["name"] + "」" for x in items) + f"卖给魔女莉莉丝,得{got}枚古币。"
    else:
        iid = params.get("item_id")
        if iid == "golden_apple" and _apple_held(s):
            item = {**GOLDEN_APPLE, "displayed": False, "origin": "witch", "secret": None}
        else:
            item = next((x for x in w["stock"] if x["id"] == iid), None)
        if item is None:
            raise IllegalAction("魔女的摊上没有这件")
        price = _witch_price(s, item, False)
        if s["coins"] < price:
            raise IllegalAction(f"古币不够(要{price}枚古币,手上{s['coins']}枚古币)")
        if len(s["inventory"]) >= _capacity(s):
            raise IllegalAction(BLOCK_TEXT["inventory_full"].format(n=len(s["inventory"]), cap=_capacity(s)))
        before = (s["coins"], s["reputation"])
        s["coins"] -= price
        if iid == "golden_apple":
            s["item_counter"] += 1
            item["id"] = f"golden_apple_{s['item_counter']}"
            w["apple_until"] = 0
            s["inventory"].append(item)
        else:
            w["stock"].remove(item)
            if item["code"] in s["collection"]:
                s["collection"][item["code"]]["count"] += 1
                s["inventory"].append(item)
            else:
                _collect(s, item)          # 首次收录照常 +2
        text = f"花{price}枚古币从魔女莉莉丝那里买下「{item['name']}」。"
    _log(s, s["day"], SHIFTS[s["shift_index"]], action_id, text, before)


def _collect(s, item):
    code = item["code"]
    first = code not in s["collection"]
    if first:
        s["collection"][code] = {
            "code": code, "name": item["name"], "story": item["story"],
            "kind": item["kind"], "rarity": item["rarity"], "first_day": s["day"],
            "first_location": item["origin"], "count": 0, "revealed": None,
        }
        s["coins"] += 2
    s["collection"][code]["count"] += 1
    s["inventory"].append(item)
    return first


START_FUNDS_MIN, START_FUNDS_MAX = 11, 66
START_FUNDS_HINT = ("开店前要掷启动资金:两颗六面骰,第一颗当十位、第二颗当个位(11-66枚古币)。"
                    "⚠️ 这一掷要由你的人类发令:先停下来,告诉人类夜铺要掷启动资金了,"
                    "等人类亲口说「掷」(或类似的话)之后,再调用 roll_start_funds,"
                    "把人类的原话填进 human_words。不得替人类发令、不得编造原话。")


def new_game(seats, seed):
    if len(seats) != 1:
        raise ValueError("口袋夜铺 v0.3 只需要一位 AI 店主")
    s = {
        "phase": "playing", "seed": seed, "seats": list(seats), "shopkeeper": seats[0],
        "day": 1, "shift_index": 0, "coins": 0, "reputation": 0,
        "shop_level": 1, "extra_capacity": 0, "inventory": [], "item_counter": 0,
        "shift_count": 0, "history": [], "diary": [], "weekly": [],
        "current_goal": "认识旧货巷的旧物,补全第一批图鉴",
        "resting": False, "last_checkpoint": None,
        "collection": {}, "encounters": {}, "unlocked_locations": ["lane"],
        "location": "lane", "pending_event": None, "event_count": 0,
        "customer": None, "customer_count": 0, "customer_book": {},
        "last_run": None,
        "start_funds_pending": True,   # 新局:等人类掷启动资金,登记前不能营业
    }
    for i in range(3):
        _collect(s, _make_item(s, "lane", f"start{i}"))
    s["coins"] = 0   # 开局钱全由启动资金那一掷决定
    _spawn_customer(s)
    return s


# 老街坊是这一局的经历,不是固定名单:只开着旧货巷/废弃车站时上过门的客人,本局一直直说需求;
# 开了第三个地点以后才初次见面的生客只留线索,来过四次成了熟客(第五次起)才直说。
NEIGHBOR_LOCATIONS = {"lane", "station"}
REGULAR_VISITS = 5


def _spawn_customer(s):
    pool = [c for c in CUSTOMERS
            if s["customer_book"].get(c[0], {}).get("visits", 0) < MAX_CUSTOMER_VISITS
            and (c[0] not in SPECIAL_CUSTOMERS or s["shop_level"] >= 3)]
    if not pool:
        s["customer"] = None
        return
    n = _number(s["seed"], "customer", s["customer_count"], s["day"])
    cid, name, request, clue, wants, base = pool[n % len(pool)]
    row = s["customer_book"].setdefault(
        cid, {"id": cid, "name": name, "request": None, "clue": clue,
              "special": cid in SPECIAL_CUSTOMERS, "first_day": s["day"],
              "visits": 0, "deals": 0, "trust": 0,
              "neighbor": set(s["unlocked_locations"]) <= NEIGHBOR_LOCATIONS})
    row["visits"] += 1
    if (row.get("neighbor", True) or cid in SPECIAL_CUSTOMERS
            or row["visits"] >= REGULAR_VISITS):
        row["request"] = request
    request = row["request"]
    s["customer_count"] += 1
    s["customer"] = {"id": cid, "name": name, "request": request, "clue": clue,
                     "visits": row["visits"], "max_visits": MAX_CUSTOMER_VISITS, "patience": 2,
                     "special": cid in SPECIAL_CUSTOMERS,
                     "_wants": list(wants), "_budget": max(3, base + n // 8 % 4 - 1 + row["trust"])}
    if cid in SPECIAL_CUSTOMERS:
        s["customer"]["_item_code"] = SPECIAL_CUSTOMERS[cid][1]


def _public_item(item):
    return {key: deepcopy(value) for key, value in item.items() if not key.startswith("_")}


CUSTOMER_HINT = ("新手提示:客人只认旧物的「类别」——就是库存里每件旧物的 kind 字段,"
                 "不看名字和故事像不像。从需求描述 request 猜他要哪一两类;远方来的生客 request 为空,"
                 "只能从线索 clue 猜(来过四次成了熟客才会直说);customer_book 里 neighbor=true 的是本局老街坊。类别对上才会买;"
                 "手上没有对的类别,就用 work_shift 的 dismiss 送客(不另收费),等下一位客人。")


def _public_customer(s):
    if s["customer"] is None:
        return None
    view = {key: value for key, value in s["customer"].items() if not key.startswith("_")}
    view["hint"] = CUSTOMER_HINT
    return view


def _locations(s):
    return [
        {"id": key, "name": loc["name"], "description": loc["description"], "cost": loc["cost"],
         "unlock_cost": loc["unlock_cost"], "required_discoveries": loc["discoveries"],
         "required_level": loc.get("level", 1),
         "required_reputation": loc.get("reputation", 0),
         "unlocked": key in s["unlocked_locations"],
         "undiscovered": sum(code not in s["collection"] for code in loc["pool"]),
         "available_undiscovered": sum(code not in s["collection"] and
                                       RARITIES[ITEM_RARITY[code]][2] <= s["shop_level"]
                                       for code in loc["pool"])}
        for key, loc in LOCATIONS.items() if key in _visible_locations(s)
    ]


def _event_view(s):
    pending = s["pending_event"]
    if pending is None:
        return None
    event = EVENTS[pending["kind"]]
    choices = []
    for key, choice in event["choices"].items():
        has_room = not (choice.get("find_item") or key in ("accept", "open")) or len(s["inventory"]) < _capacity(s)
        choices.append({"id": key, **choice,
                        "available": s["coins"] >= choice["cost"] and has_room})
    return {"id": pending["id"], "name": event["name"], "text": event["text"], "choices": choices}


NEWCOMER_SHIFTS = 28   # 头两周
NEWCOMER_ADVICE = ("建议:头两周先用 work_shift 一班一班地淘,别急着连淘。"
                   "一班一个故事、一位客人一位客人地认识,才是夜铺的乐趣;连淘会把进度刷得太快。"
                   "熟悉以后再用 run_shifts 省事。")


def _legal_actions(s):
    if s.get("start_funds_pending"):
        return [{"action_id": "roll_start_funds", "params": {"human_words": START_FUNDS_HINT}}]
    if s["resting"]:
        return [{"action_id": "reopen_shop", "params": {}}]
    if s["pending_event"]:
        return [{"action_id": "choose_event", "params": {
                    "event_id": s["pending_event"]["id"], "choice": _event_view(s)["choices"]}},
                {"action_id": "close_for_now", "params": {}}]
    actions = [
        {"action_id": "work_shift", "params": {
            "focus": FOCI, "item_id": "sell/repair/curate/recycle 必填,从库存选",
            "asking_price": "sell 必填正整数;店主自己报价",
            "location": "scavenge 可选已解锁地点 id",
            "goal": "可选,1-60字;表达也可省略", "mood": MOODS,
            "public_line": "可选,1-80字;沉默是正常玩法"}},
        {"action_id": "run_shifts", "params": {
            "focus": ["scavenge", "repair", "tidy"], "count": "1-6",
            "item_id": "repair 必填", "location": "scavenge 可选已解锁地点",
            "reserve": "非负整数,含当班维护费的现金保留线",
            "stop_on": '可选字符串或数组:new/rare/event;如 "new" 或 ["new","rare"];'
                       '省略默认 ["new","rare","event"];[] 不因这些标记停班,待选择事件仍停',
            **({"advice": NEWCOMER_ADVICE} if s["shift_count"] < NEWCOMER_SHIFTS else {})}},
        {"action_id": "close_for_now", "params": {}},
    ]
    if _witch_view(s):
        actions.append({"action_id": "witch_sell", "params": {"item_ids": "要卖给魔女的库存 id 数组,本次最多2件"}})
        actions.append({"action_id": "witch_buy", "params": {"item_id": "魔女摊上 stock 里的 id"}})
    if any(key not in s["unlocked_locations"] for key in _visible_locations(s)):
        actions.append({"action_id": "unlock_location", "params": {"location": _locations(s)}})
    return actions


def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    public = {
        "phase": s["phase"], "day": s["day"], "shift": SHIFTS[s["shift_index"]],
        "coins": s["coins"], "reputation": s["reputation"], "shop_level": s["shop_level"],
        "capacity": _capacity(s), "inventory": [_public_item(item) for item in s["inventory"]],
        "current_goal": s["current_goal"], "resting": s["resting"],
        "start_funds_pending": bool(s.get("start_funds_pending")),
        "last_checkpoint": deepcopy(s["last_checkpoint"]),
        "customer": _public_customer(s), "customer_book": deepcopy(list(s["customer_book"].values())),
        "customer_collection": {"found": len(s["customer_book"]), "total": len(CUSTOMERS),
                                "visit_limit": MAX_CUSTOMER_VISITS,
                                "retired": sum(row["visits"] >= MAX_CUSTOMER_VISITS
                                               for row in s["customer_book"].values())},
        "rarities": [{"id": key, "label": label, "min_level": level,
                      "total": sum(rarity == key for rarity in ITEM_RARITY.values()),
                      "found": sum(row["rarity"] == key for row in s["collection"].values())}
                     for key, (label, weight, level) in RARITIES.items()],
        "weekly": deepcopy(s["weekly"][-8:]), "diary": deepcopy(s["diary"][-8:]),
        "recent_history": deepcopy(s["history"][-6:]), "journal_total": len(s["history"]),
        "collection": {"found": len(s["collection"]), "total": len(ITEMS),
                       "revealed": sum(bool(row["revealed"]) for row in s["collection"].values()),
                       "entries": deepcopy(list(s["collection"].values()))},
        "encounters": {"found": len(s["encounters"]), "total": len(EVENTS),
                       "entries": deepcopy(list(s["encounters"].values()))},
        "locations": _locations(s), "location": s["location"],
        "witch": _witch_view(s),
        "pending_event": _event_view(s), "last_run": deepcopy(s["last_run"]),
    }
    return {"public_state": public,
            "private_state": {"role": "shopkeeper", "resume_summary": {
                "day": s["day"], "shift": SHIFTS[s["shift_index"]], "goal": s["current_goal"],
                "coins": s["coins"], "discoveries": len(s["collection"]),
                "pending_event": _event_view(s),
                "last_events": [entry["text"] for entry in s["history"][-3:]]}},
            "legal_actions": [] if s["phase"] == "finished" else _legal_actions(s),
            "waiting_for": [] if s["resting"] or s["phase"] == "finished" else [s["shopkeeper"]]}


def history_since(s, after_seq):
    # 显示器按游标读取全部公开日志,批量经营也不丢班次。
    return deepcopy(s["history"][after_seq:after_seq + 100])


def _log(s, day, shift, focus, text, before, **extra):
    s["history"].append({
        "seq": len(s["history"]) + 1, "day": day, "shift": shift, "focus": focus,
        "text": text, "coins_delta": s["coins"] - before[0],
        "reputation_delta": s["reputation"] - before[1],
        "goal": s["current_goal"], "customer": deepcopy(_public_customer(s)), **extra,
    })


def _text_param(params, key, maximum):
    value = params.get(key)
    if value is not None and (not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum):
        raise IllegalAction(f"{key} 须为1到{maximum}字")
    return value.strip() if value is not None else None


def _validate_work(s, params):
    focus = params.get("focus")
    if focus not in FOCI:
        raise IllegalAction("未知经营动作")
    if focus in ("sell", "dismiss") and s["customer"] is None:
        raise IllegalAction("当前没有可接待的客人；仍可淘货、修理、回收或扩建")
    _text_param(params, "goal", 60)
    _text_param(params, "public_line", 80)
    if params.get("mood") is not None and params["mood"] not in MOODS:
        raise IllegalAction("未知心情")
    if focus in ("sell", "repair", "curate", "recycle"):
        item = next((item for item in s["inventory"] if item["id"] == params.get("item_id")), None)
        if item is None:
            raise IllegalAction("请选库存中的旧物")
        if focus == "sell":
            price = params.get("asking_price")
            if type(price) is not int or price <= 0:
                raise IllegalAction("asking_price 必须为正整数")
    if focus == "scavenge":
        location = params.get("location", s["location"])
        if not isinstance(location, str) or location not in s["unlocked_locations"]:
            raise IllegalAction("请先解锁淘货地点")


def _work_cost(s, params):
    focus = params["focus"]
    if focus == "scavenge":
        return LOCATIONS[params.get("location", s["location"])]["cost"]
    if focus == "repair":
        return 1
    if focus == "upgrade":
        return 10 * s["shop_level"]
    return 0


BLOCK_TEXT = {
    "inventory_full": "货架满了({n}/{cap}件),淘不回新东西。先卖出、回收(recycle)或扩建(upgrade)腾出位置再淘货。",
    "repair_complete": "这件已经修到最好(完好度3/3),不用再修了。",
    "display_full": "陈列位满了或这件已在陈列,先撤下别的再陈列。",
    "shop_maximum": "店铺已经扩建到最高级。",
    "insufficient_coins": "古币不够这一班的花销(需要{cost}枚古币,手上{coins}枚古币)。",
    "reserve": "再做下去手上的古币会低于你设的保留线 reserve,所以没有开工。",
}


def _block_text(s, params, block):
    return BLOCK_TEXT[block].format(n=len(s["inventory"]), cap=_capacity(s),
                                    cost=_work_cost(s, params), coins=s["coins"])


def _work_block(s, params):
    focus = params["focus"]
    if focus == "scavenge" and len(s["inventory"]) >= _capacity(s):
        return "inventory_full"
    if focus in ("repair", "curate"):
        item = next(item for item in s["inventory"] if item["id"] == params["item_id"])
        if focus == "repair" and item["condition"] >= 3:
            return "repair_complete"
        if focus == "curate" and (item["displayed"] or
                sum(bool(x["displayed"]) for x in s["inventory"]) >= s["shop_level"] + 1):
            return "display_full"
    if focus == "upgrade" and s["shop_level"] >= MAX_SHOP_LEVEL:
        return "shop_maximum"
    if s["coins"] < _work_cost(s, params):
        return "insufficient_coins"
    return None


def apply(full_state, seat_id, action_id, params):
    s = deepcopy(full_state)
    if seat_id != s["shopkeeper"] or seat_id not in s["seats"]:
        raise IllegalAction("只有 AI 店主可以操作;网页仅供观看")
    if s["phase"] != "playing":
        raise IllegalAction("本局已结束")
    if not isinstance(params, dict):
        raise IllegalAction("params 须是对象")
    if action_id == "close_for_now":
        if s["resting"]:
            raise IllegalAction("已经歇业")
        s["resting"] = True
        s["last_checkpoint"] = {"day": s["day"], "shift": SHIFTS[s["shift_index"]],
                                "coins": s["coins"], "goal": s["current_goal"],
                                "week": s["weekly"][-1]["week"] if s["weekly"] else None}
        return s
    if action_id == "reopen_shop":
        if not s["resting"]:
            raise IllegalAction("店铺已经开门")
        s["resting"] = False
        return s
    if s["resting"]:
        raise IllegalAction("请先 reopen_shop 续档")
    s["last_run"] = None
    if s.get("start_funds_pending"):
        if action_id != "roll_start_funds":
            raise IllegalAction("还没掷启动资金。" + START_FUNDS_HINT)
        words = params.get("human_words")
        if not isinstance(words, str) or not words.strip():
            raise IllegalAction("human_words 要填人类叫你掷骰时的原话。" + START_FUNDS_HINT)
        tens, ones = (_number(s["seed"], "start_funds", i) % 6 + 1 for i in (0, 1))
        s["coins"] = tens * 10 + ones
        s["start_funds_pending"] = False
        _log(s, s["day"], SHIFTS[s["shift_index"]], "start_funds",
             f"人类发令「{words.strip()[:40]}」,两颗骰子落下:十位{tens}、个位{ones}"
             f"——启动资金{s['coins']}枚古币。夜铺开门了。", (0, s["reputation"]))
        return s
    if action_id == "roll_start_funds":
        raise IllegalAction("启动资金已经掷过了")
    if action_id == "choose_event":
        _choose_event(s, params)
    elif s["pending_event"]:
        raise IllegalAction("请先处理眼前事件,也可歇业后下次继续")
    elif action_id == "unlock_location":
        _unlock(s, params)
    elif action_id in ("witch_sell", "witch_buy"):
        _witch_trade(s, action_id, params)
    elif action_id in ("work_shift", "run_shifts"):
        _validate_work(s, params)
        if action_id == "work_shift":
            block = _work_block(s, params)
            if block:
                raise IllegalAction(_block_text(s, params, block))
            _work_shift(s, params)
        else:
            _run_shifts(s, params)
    else:
        raise IllegalAction(f"没有这个动作:{action_id}")
    return s


def _run_shifts(s, params):
    if params["focus"] not in ("scavenge", "repair", "tidy"):
        raise IllegalAction("连续行动限淘货、修理和整理;出售由店主逐件决定")
    count = params.get("count", 1)
    reserve = params.get("reserve", 0)
    stops = params.get("stop_on", ["new", "rare", "event"])
    if isinstance(stops, str):
        stops = [stops]
    if type(count) is not int or not 1 <= count <= MAX_BATCH:
        raise IllegalAction("count 须为1到6")
    if type(reserve) is not int or reserve < 0:
        raise IllegalAction("reserve 须为非负整数")
    if not isinstance(stops, list) or any(x not in ("new", "rare", "event") for x in stops):
        raise IllegalAction('stop_on 须为 new/rare/event 字符串或由它们组成的数组;'
                            '如 "new"、["new","rare"] 或 []')
    done, reason, start = 0, "count", len(s["history"])
    for _ in range(count):
        block = _work_block(s, params)
        upkeep = s["shop_level"] if s["shift_index"] == 1 else 0
        known_income = 2 + s["shop_level"] if params["focus"] == "tidy" else 0
        # 不把未知奖励当作已到手的钱;边界在真正花钱前生效。
        if block or s["coins"] + known_income - _work_cost(s, params) - upkeep < reserve:
            reason = block or "reserve"
            break
        flags = _work_shift(s, params)
        done += 1
        if s["pending_event"]:
            reason = "decision"
            break
        if flags.get("witch"):
            reason = "witch"
            break
        hit = next((key for key in ("event", "new", "rare") if key in stops and flags[key]), None)
        if hit:
            reason = hit
            break
    if done == 0 and reason in BLOCK_TEXT:
        # 一班都没做成:当面拒绝并说明原因,不再静默返回"成功"
        raise IllegalAction(_block_text(s, params, reason))
    s["last_run"] = {"requested": count, "completed": done, "stop_reason": reason,
                     "stop_text": (_block_text(s, params, reason) if reason in BLOCK_TEXT else None),
                     "from_seq": start + 1 if done else None, "to_seq": len(s["history"]),
                     "highlights": [row["text"] for row in s["history"][start:]
                                    if row.get("new") or row.get("rare") or row.get("event")]}


def _work_shift(s, params):
    before = (s["coins"], s["reputation"])
    day, shift = s["day"], SHIFTS[s["shift_index"]]
    customer = deepcopy(_public_customer(s))
    customer_count = s["customer_count"]
    offer = None
    if params["focus"] == "sell":
        item = next(x for x in s["inventory"] if x["id"] == params["item_id"])
        offer = {"item_name": item["name"], "asking_price": params["asking_price"]}
    flags = {"new": False, "rare": False, "event": False}
    if s.get("witch"):
        s["witch"]["visit"] = None       # 魔女只等到下一班开始
    report = _do_focus(s, params, flags)
    if params["focus"] == "scavenge":
        meet = _witch_meet(s, params.get("location", s["location"]))
        if meet:
            report += meet
            flags["witch"] = True
    if params.get("goal") is not None:
        s["current_goal"] = params["goal"].strip()
    ambient = AMBIENT[_number(s["seed"], "ambient", s["shift_count"]) % len(AMBIENT)]
    s["shift_count"] += 1
    _witch_tick(s)
    event_text = _maybe_event(s)
    if event_text:
        report += " " + event_text
        flags["event"] = True
    if s["shift_index"] == 1:
        upkeep = s["shop_level"]   # 每天维护费 = 店铺等级
        paid = min(upkeep, s["coins"])
        s["coins"] -= paid
        if paid < upkeep:
            s["reputation"] = max(0, s["reputation"] - 1)
        report += f" 打烊维护应付{upkeep}枚古币,实际付{paid}枚古币。"
        s["diary"].append({"day": day, "text": f"打烊时手上{s['coins']}枚古币,声望{s['reputation']}。",
                           "upkeep": paid})
        if day % 7 == 0:
            s["weekly"].append({"week": day // 7, "through_day": day, "coins": s["coins"],
                "reputation": s["reputation"], "shop_level": s["shop_level"],
                "inventory": len(s["inventory"]), "deals": sum(x["deals"] for x in s["customer_book"].values()),
                "discoveries": len(s["collection"]), "encounters": len(s["encounters"])})
        s["day"] += 1
        s["shift_index"] = 0
    else:
        s["shift_index"] = 1
    reaction = None
    if params.get("mood") is not None or params.get("public_line") is not None:
        reaction = {"mood": params.get("mood"), "text": _text_param(params, "public_line", 80)}
    _log(s, day, shift, params["focus"], report, before, ambient=ambient, reaction=reaction,
         customer=customer, offer=offer,
         customer_arrived=deepcopy(_public_customer(s)) if s["customer_count"] != customer_count else None,
         **flags)
    return flags


def _do_focus(s, params, flags):
    focus = params["focus"]
    item = next((x for x in s["inventory"] if x["id"] == params.get("item_id")), None)
    if focus == "scavenge":
        location = params.get("location", s["location"])
        s["location"] = location
        s["coins"] -= LOCATIONS[location]["cost"]
        found = _make_item(s, location, f"find{s['shift_count']}")
        flags["new"] = _collect(s, found)
        flags["rare"] = found["rarity"] in ("rare", "ancient", "heirloom")
        prefix = "新发现,图鉴收录+2枚古币。" if flags["new"] else "这件见过,图鉴数量+1。"
        if flags["new"] and len(s["collection"]) == len(ITEMS):
            prefix += " 异物志全部物种已发现！还可继续补完修复秘密。"
        return f"从{LOCATIONS[location]['name']}带回「{found['name']}」。{prefix} {found['story']}"
    if focus == "repair":
        s["coins"] -= 1
        item["condition"] += 1
        item["value"] += 2
        report = f"修补「{item['name']}」,完好度{item['condition']}/3。"
        if item["condition"] == 3:
            item["secret"] = item["_secret"]
            row = s["collection"][item["code"]]
            first_reveal = row["revealed"] is None
            if first_reveal:
                row["revealed"] = item["secret"]
                row["revealed_day"] = s["day"]
                s["coins"] += 2
                flags["new"] = True
                report += " 图鉴首次揭秘,获得2枚古币。"
                if sum(bool(x["revealed"]) for x in s["collection"].values()) == len(ITEMS):
                    report += " 异物志全部揭秘！这间店已经见证了每一种旧物的另一面。"
            item["value"] += 3
            bonus = REPAIR_REPUTATION.get(item["rarity"], 0)
            if bonus and first_reveal:      # 同一种宝物只在第一次修满时加声望,重复货刷不了
                s["reputation"] += bonus
                report += f" 修好了一件{RARITIES[item['rarity']][0]}旧物,街坊口耳相传,声望+{bonus}。"
            report += f" 完全修复后才发现:{item['secret']}"
        return report
    if focus == "sell":
        c = s["customer"]
        price = params["asking_price"]
        # 完好程度和异能确实影响出价上限,昂贵破物不能无限高价倒卖。
        ceiling = min(c["_budget"], item["value"] + item["condition"] + s["shop_level"])
        matches = item["code"] == c["_item_code"] if "_item_code" in c else item["kind"] in c["_wants"]
        if matches and price <= ceiling:
            s["coins"] += price
            s["reputation"] += 1
            row = s["customer_book"][c["id"]]
            row["deals"] += 1
            row["trust"] = min(5, row["trust"] + 1)
            s["inventory"].remove(item)
            report = f"{c['name']}付了{price}枚古币,带走「{item['name']}」。图鉴记录保留。"
            _spawn_customer(s)
            return report
        c["patience"] -= 1
        report = (f"{c['name']}表示这类旧物不合需要。" if not matches
                  else f"{c['name']}觉得报价偏高,还没有成交。")
        if c["patience"] == 0:
            report += " 客人告辞了。"
            _spawn_customer(s)
        return report
    if focus == "recycle":
        price = max(1, item["value"] // 3)
        s["coins"] += price
        s["inventory"].remove(item)
        return f"把「{item['name']}」作为零件回收,得{price}枚古币。图鉴记录保留。"
    if focus == "dismiss":
        name = s["customer"]["name"]
        _spawn_customer(s)
        return f"向{name}说明暂时无货,记下需求送客。" + ("另一位客人进门。" if s["customer"] else "眼下没有新的来客，店铺仍可经营。")
    if focus == "curate":
        item["displayed"] = True
        s["reputation"] += 1
        return f"「{item['name']}」放进橱窗,暂不出售。"
    if focus == "upgrade":
        cost = 10 * s["shop_level"]
        s["coins"] -= cost
        s["shop_level"] += 1
        if s["customer"] is None:
            _spawn_customer(s)
        return f"花{cost}枚古币扩建到{s['shop_level']}级。"
    income = 2 + s["shop_level"]
    s["coins"] += income
    return f"整理货架并承接街坊的小修补,挣得{income}枚古币。"


def _record_event(s, key, outcome=None, text=None):
    event = EVENTS[key]
    row = s["encounters"].setdefault(key, {
        "id": key, "name": event["name"], "text": event["text"],
        "first_day": s["day"], "count": 0, "outcomes": {},
    })
    if outcome is None:
        row["count"] += 1
    else:
        row["outcomes"][outcome] = text


def _maybe_event(s):
    n = _number(s["seed"], "event", s["shift_count"])
    if n % 4:
        return ""
    pool = [key for key, event in EVENTS.items() if event.get("level", 1) <= s["shop_level"]]
    key = pool[(n // 4) % len(pool)]
    event = EVENTS[key]
    s["event_count"] += 1
    _record_event(s, key)
    if "choices" in event:
        s["pending_event"] = {"id": f"event_{s['event_count']}", "kind": key,
                              "_location": s["location"]}
        return f"街巷见闻「{event['name']}」:{event['text']} 等待店主选择。"
    s["coins"] += event.get("coins", 0)
    s["reputation"] += event.get("reputation", 0)
    _record_event(s, key, "happened", event["text"])
    return f"街巷见闻「{event['name']}」:{event['text']}"


def _choose_event(s, params):
    pending = s["pending_event"]
    if pending is None or params.get("event_id") != pending["id"]:
        raise IllegalAction("请回应当前事件")
    key, choice = pending["kind"], params.get("choice")
    event = EVENTS[key]
    if not isinstance(choice, str) or choice not in event["choices"]:
        raise IllegalAction("请选事件中列出的选项")
    option = event["choices"][choice]
    cost = option["cost"]
    if s["coins"] < cost:
        raise IllegalAction("现金不足,可以选择免费选项")
    gets_item = option.get("find_item") or choice in ("accept", "open")
    if gets_item and len(s["inventory"]) >= _capacity(s):
        raise IllegalAction("货架已满,可选择不收下")
    before = (s["coins"], s["reputation"])
    s["coins"] -= cost
    s["coins"] += option.get("coins", 0)
    s["reputation"] += option.get("reputation", 0)
    first = rare = False
    if gets_item:
        item = _make_item(s, pending["_location"], pending["id"])
        first = _collect(s, item)
        rare = item["rarity"] in ("rare", "ancient", "heirloom")
        report = f"打开后发现「{item['name']}」。" + ("首次收录,获得2枚古币。" if first else "补记到图鉴。")
        if first and len(s["collection"]) == len(ITEMS):
            report += " 异物志全部物种已发现！"
    elif "outcome" in option:
        report = option["outcome"]
    elif choice == "trade":
        s["coins"] += 1
        report = "收货人带走小匣,留下一枚古币。"
    else:
        report = "店主选择暂不接下这件事,店铺继续营业。"
    _record_event(s, key, choice, report)
    s["pending_event"] = None
    _log(s, s["day"], SHIFTS[s["shift_index"]], "choose_event", report, before,
         event=True, new=first, rare=rare, reaction=None, ambient="",
         event_name=event["name"], choice=event["choices"][choice]["label"])


def _unlock(s, params):
    key = params.get("location")
    if not isinstance(key, str) or key not in _visible_locations(s):
        raise IllegalAction("未知地点")
    if key in s["unlocked_locations"]:
        raise IllegalAction("地点已经解锁")
    loc = LOCATIONS[key]
    if (len(s["collection"]) < loc["discoveries"] or s["coins"] < loc["unlock_cost"]
            or s["shop_level"] < loc.get("level", 1) or s["reputation"] < loc.get("reputation", 0)):
        raise IllegalAction(f"发现种数、店铺等级、声望或现金不足(需要声望{loc.get('reputation', 0)})")
    before = (s["coins"], s["reputation"])
    s["coins"] -= loc["unlock_cost"]
    s["unlocked_locations"].append(key)
    text = f"打通前往{loc['name']}的淘货路线。"
    if key == SECRET:
        s["secret_opened_day"] = s["day"]
        text += " 灯塔亮起的那晚,魔女莉莉丝抱着金苹果出门了——这七天里碰见她,也许会有好事。"
    _log(s, s["day"], SHIFTS[s["shift_index"]], "unlock_location", text, before, ambient="", reaction=None)
