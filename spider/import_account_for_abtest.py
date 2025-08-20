"""
这100个账号用来校验，精确分配单独的代理路线，路线不能重复
速度加速到最大来测试

"""

data = """
SXbQWoQz@usportacad.com peTYZKhJ SXbQWoQz@outlook.com
aQCgANMK@usportacad.com YzTpHvCG aQCgANMK@outlook.com
wpGYcTxi@usportacad.com VUNRefyz wpGYcTxi@outlook.com
MuiGUMrK@usportacad.com xGbCZGme MuiGUMrK@outlook.com
UEcJvczQ@usportacad.com xTbcGjlU UEcJvczQ@outlook.com
ZzKTMUiK@usportacad.com njMgYiPe ZzKTMUiK@outlook.com
ZuUEbjCq@usportacad.com DFPNCEAk ZuUEbjCq@outlook.com
JgLmiMOq@usportacad.com qPHyPQxn JgLmiMOq@outlook.com
PBsoSSfF@usportacad.com rOpABUnR PBsoSSfF@outlook.com
WFPiTclu@usportacad.com ctoXBLPD WFPiTclu@outlook.com
JEDLXshK@usportacad.com mluxDMKD JEDLXshK@outlook.com
xnjFYqNO@usportacad.com oajSHxZw xnjFYqNO@outlook.com
WFEpPYYL@usportacad.com jzAoYtnz WFEpPYYL@outlook.com
oWjLmoCP@usportacad.com CZPMzphf oWjLmoCP@outlook.com
GvjKVARY@usportacad.com oSrcXKFQ GvjKVARY@outlook.com
ZvePAQVc@usportacad.com PLYrqWWv ZvePAQVc@outlook.com
wiacCmAZ@usportacad.com uYQBXaXE wiacCmAZ@outlook.com
sKteaviC@usportacad.com zIMMTOVH sKteaviC@outlook.com
iOBVPPUE@usportacad.com aCdBfQxQ iOBVPPUE@outlook.com
dQEjbZFJ@usportacad.com HSoySVUC dQEjbZFJ@outlook.com
RyftWMea@usportacad.com rISuvxJT RyftWMea@outlook.com
OpITsGmI@usportacad.com IrcbrhgA OpITsGmI@outlook.com
xaTQvoUU@usportacad.com BAHZeRPd xaTQvoUU@outlook.com
zVpuvYHS@usportacad.com bOYGVWUu zVpuvYHS@outlook.com
bHSOUWkm@usportacad.com ziaOLFqt bHSOUWkm@outlook.com
uhqttrRz@usportacad.com bbnXItjM uhqttrRz@outlook.com
KxwJxEzA@usportacad.com lXHAicdK KxwJxEzA@outlook.com
YJUMrQGX@usportacad.com CgLRlRTQ YJUMrQGX@outlook.com
MwcorSPD@usportacad.com lfWDLpOM MwcorSPD@outlook.com
nloVBbnM@usportacad.com wwJMgGPs nloVBbnM@outlook.com
nQNkMltV@usportacad.com DRqwNqKw nQNkMltV@outlook.com
AKHFVQUw@usportacad.com izWUVUoO AKHFVQUw@outlook.com
DIaBnWZh@usportacad.com lyfRXbdt DIaBnWZh@outlook.com
nlRfGLpT@usportacad.com ZkkAMJjy nlRfGLpT@outlook.com
ItRNPlEV@usportacad.com lCfWoEUq ItRNPlEV@outlook.com
vIeYypDf@usportacad.com oCcTDfwo vIeYypDf@outlook.com
lnnYzSoD@usportacad.com FNealUpa lnnYzSoD@outlook.com
CinttkNN@usportacad.com saTfDCfm CinttkNN@outlook.com
EjLbQkIV@usportacad.com mDLdbjLk EjLbQkIV@outlook.com
rJNnoqnO@usportacad.com kbKcnOjm rJNnoqnO@outlook.com
rtRVkoSE@usportacad.com mCGXlETp rtRVkoSE@outlook.com
KQbLWits@usportacad.com QaLWmOmC KQbLWits@outlook.com
JFfMuati@usportacad.com UkhVtKfC JFfMuati@outlook.com
JYEyibIU@usportacad.com poDURfca JYEyibIU@outlook.com
bDadXpPt@usportacad.com XpGgnuKI bDadXpPt@outlook.com
xiryINfM@usportacad.com nkOLSYLr xiryINfM@outlook.com
mSRWVpop@usportacad.com FcTWctfc mSRWVpop@outlook.com
hXhHXUey@usportacad.com bSrFcaMI hXhHXUey@outlook.com
BbJOfRjR@usportacad.com rlRlDVXx BbJOfRjR@outlook.com
OobdLCri@usportacad.com vGOnrvHV OobdLCri@outlook.com
NjmPGveY@usportacad.com hPRKmKUl NjmPGveY@outlook.com
XokNnAhz@usportacad.com XmGuzEqI XokNnAhz@outlook.com
PkqkjtwH@usportacad.com ogMhrOyQ PkqkjtwH@outlook.com
ZwZLaiBq@usportacad.com qxoTBGNh ZwZLaiBq@outlook.com
ezRigPtg@usportacad.com qmRdEngS ezRigPtg@outlook.com
fjFFXiyO@usportacad.com qRdFPiox fjFFXiyO@outlook.com
awpQwKED@usportacad.com ZTvFemko awpQwKED@outlook.com
XmiBRlAr@usportacad.com XHpKmSqm XmiBRlAr@outlook.com
DAGANoww@usportacad.com TeJpGVIl DAGANoww@outlook.com
uGFGvSwE@usportacad.com MbONiCIa uGFGvSwE@outlook.com
NfMHBKWg@usportacad.com FdpNwgZv NfMHBKWg@outlook.com
OgKwkXEO@usportacad.com vcGPKnDf OgKwkXEO@outlook.com
PplhilcN@usportacad.com tdzseKhe PplhilcN@outlook.com
woGLmucc@usportacad.com AEVfAVlB woGLmucc@outlook.com
oeUbjrsL@usportacad.com OLMRZCMv oeUbjrsL@outlook.com
xYcIjoYH@usportacad.com mXMSZMYK xYcIjoYH@outlook.com
izYTulLg@usportacad.com crceOYDm izYTulLg@outlook.com
TYiQanuI@usportacad.com kzamSgLj TYiQanuI@outlook.com
pIzGIrXg@usportacad.com SDosmuNp pIzGIrXg@outlook.com
TgBNHmyV@usportacad.com nbNaewjm TgBNHmyV@outlook.com
ZuuAwmeJ@usportacad.com BHgdulqL ZuuAwmeJ@outlook.com
MwcPKwvh@usportacad.com lHmSBTAC MwcPKwvh@outlook.com
WewpNiGq@usportacad.com GSLTaFQD WewpNiGq@outlook.com
FHwTIVwo@usportacad.com qCzTROAD FHwTIVwo@outlook.com
hTijFdET@usportacad.com wJtJvUTQ hTijFdET@outlook.com
pZziXHrB@usportacad.com qOCeTSqb pZziXHrB@outlook.com
qCTBtsYa@usportacad.com sblVJqyc qCTBtsYa@outlook.com
RrAehEYk@usportacad.com iPouKYHT RrAehEYk@outlook.com
jJcpmjqt@usportacad.com ytwjdWKv jJcpmjqt@outlook.com
eiEwUtIe@usportacad.com TOGYRcJX eiEwUtIe@outlook.com
pMTqpelL@usportacad.com QGSyjYLQ pMTqpelL@outlook.com
pYlJTuOW@usportacad.com akqXvYFt pYlJTuOW@outlook.com
zSxXyHhS@usportacad.com HlDGHvta zSxXyHhS@outlook.com
biqCGJUH@usportacad.com asktesBS biqCGJUH@outlook.com
lTCXfhBB@usportacad.com zpmdbmNt lTCXfhBB@outlook.com
gkYfhiEO@usportacad.com soBbpMlT gkYfhiEO@outlook.com
QeiUKuWt@usportacad.com YYcxrHdh QeiUKuWt@outlook.com
ItbpkZyR@usportacad.com nHrWlcwI ItbpkZyR@outlook.com
LlUTPYIu@usportacad.com FidDbvYs LlUTPYIu@outlook.com
JJXbCKYG@usportacad.com osYjcYBM JJXbCKYG@outlook.com
WQAmBhIa@usportacad.com mjXmhGPV WQAmBhIa@outlook.com
QiLZtjgP@usportacad.com nHYyacrn QiLZtjgP@outlook.com
IcyWJDaZ@usportacad.com aNBcQvpK IcyWJDaZ@outlook.com
JAtPfWWi@usportacad.com iycNlknO JAtPfWWi@outlook.com
VzEESidR@usportacad.com QORjqdlD VzEESidR@outlook.com
acnONyrU@usportacad.com AprgqySE acnONyrU@outlook.com
GgYZoklM@usportacad.com KYtcwFtO GgYZoklM@outlook.com
cjKyDTtY@usportacad.com pxsgnHue cjKyDTtY@outlook.com
tXoNrmje@usportacad.com EBJbffbZ tXoNrmje@outlook.com
FLLcSdkm@usportacad.com eIPIEYMR FLLcSdkm@outlook.com
"""



# 每次新增替换上面的数据（来自于飞书文档：）
# https://svv17uppgnx.feishu.cn/wiki/P7Vewa9Lwi5Fv8k2tk3cKDwQnz2?sheet=oxcnda

from pymongo import MongoClient
import hashlib
from datetime import datetime


def md5(text):
    if not text:
        return text
    m = hashlib.md5()
    m.update(text.encode('utf-8'))
    return m.hexdigest()
dataset = []

# 1. 连接 MongoDB
client = MongoClient("mongodb://192.168.0.123:27017")
db = client["smolecule"]
collection = db["ast_browser_auth_data2"]

now = datetime.now()
now_str = now.strftime("%Y-%m-%d %H:%M:%S")

# 2. 要插入的数据
dataArr = data.split('\n')
for item in dataArr:
    if item:
        itemdata = item.split(' ')
        email = itemdata[0]
        std_email = email.lower()
        pwd = itemdata[1]
        email1 = itemdata[2]
        exists_data = collection.find_one({"email": email})
        if not exists_data:
            insert_result = collection.insert_one({
                "email": email,
                "std_email": std_email,
                "account": md5(std_email),
                "email_assist": email1,
                "password": pwd,
                "account_type": "pro",
                "sync_status": "waiting",
                "register_time": now_str,
            })
            print(f"插入的文档 Email: {email}")
