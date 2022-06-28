# -*- coding:gbk -*-
#import chardet
import sys,os,time,subprocess
import shutil
import imaplib
from email.mime.text import MIMEText
from email.header import Header
import AutoDeploy as auto
import ftplib
import pymysql
import re
import urllib

######################################## 配置区域 ##############################################################
version = '1.7.6'
project = auto.project
publishdir = auto.publishdir

#发布FTP外网信息
ftpurl = 'x.x.x.x'
ftpuser = 'xx'
ftppwd = 'xx'
if project == 24:
    publishdir_public = '/ss/paladin/监管报告版本'
else:
    publishdir_public = '/ss/paladin'

if project == 24:
    publishdir_public = '/ss/paladin/监管报告版本'
    publishdir_private = 'http://192.168.72.99/svn/Repository/项目开发/发布版本/监管报表'
    resourcename_dir = time.strftime('%Y%m%d-',time.localtime())+'v'+version
else:
    publishdir_public = '/ss/paladin'
    publishdir_private = 'http://192.168.72.99/svn/Repository/项目开发/发布版本'
    resourcename_dir = 'v'+version #银行间

resourcename_arc = resourcename_dir + '.zip'

#邮箱信息
user = 'xx' #发件人
passwd = 'xx' #发件人密码
To = ('实施部（深圳）','实施部（北京）')#收件人-获取禅道部门
Cc = ('帕拉丁测试组','帕拉丁分析组','帕拉丁场外组')#抄送人-获取禅道部门

################################################################################################################


class EmailWriter():
    def __init__(self,host,port,user,pwd):
        try:
            self.user=user
            self.conn = imaplib.IMAP4_SSL(host, port)
            print(user)
            print(pwd)
            self.conn.login(self.user, pwd)
            print('邮件初始化成功.')
            self.initialized = True
        except Exception as ex:
            print('邮件初始化错误!'+ex)
            self.initialized = False
            
    # 写邮件草稿
    def writedraft(self,title,content,rec,cc=None):
        print('正在编写邮件草稿...')
        if self.initialized:
            try:
                #print(conn.select('Drafts')[1][0])#查询草稿文件夹有多少条记录
                message = MIMEText(content, 'html', 'utf-8')
                message['From'] = self.user#发送人
                message['To'] =  rec#收件人
                if cc:
                    message['Cc'] =  cc#抄送人
                message['Subject'] = Header(title, 'utf-8')
                self.conn.append('Drafts','',imaplib.Time2Internaldate(time.time()),message.as_bytes())
            except Exception as ex:
                print(ex)
            print('邮件草稿编写完成,请登录邮箱【'+self.user+'】检查/发送邮件.')
        else:
            print('邮件服务未初始化!')


    # 根据部门获取禅道的收件人
    def getrecipient(self,dept):
        depts = '\'' +','.join(dept).replace(',','\',\'') + '\''
        sql = 'select group_concat(u.email order by u.id) from zt_user u join zt_dept d on u.dept=d.id where d.name in({dept}) and u.deleted=\'0\''.format(dept=depts)
        #禅道链接
        con = pymysql.connect('112.74.115.12','root','Scxx_150906','zentao_qy',charset='utf8')
        cur = con.cursor()
        cur.execute(sql)
        data = cur.fetchall()
        cur.close()
        con.close()
        print(data[0][0])
        return data[0][0]

    # 查询禅道数据库，获取版本发布清单
    def getversion(self,version):
        sql = 'SELECT D.NAME AS 版本号, "需求" AS 类型, S.ID AS 编号, S.TITLE AS 名称 '\
                    'FROM ZT_STORY S, ZT_BUILDSTORYBUG SB, ZT_BUILD D, ZT_STORYRELATION SR, ZT_KEYWORDS KW '\
                    'WHERE S.ID = SB.RELATEID AND SB.BUILD = D.ID AND S.ID = SR.STORY AND SR.CUSTOMER = KW.ID '\
                    'AND SB.TYPE = "story" AND S.PRODUCT {project} AND S.DELETED = "0" AND S.STATUS <> "closed" '\
                    'AND D.DELETED = "0" AND NOT D.NAME LIKE "PT%" AND D.NAME = {version}'\
                    'UNION ALL '\
                    'SELECT C1. NAME 版本号, "BUG" 类型, A.ID 编号, A.TITLE 名称 '\
                    'FROM ZT_BUG A LEFT JOIN ZT_BUILDSTORYBUG C ON A.ID = C.RELATEID LEFT JOIN ZT_BUILD C1 ON A.PRODUCT = C1.PRODUCT '\
                    'AND C.BUILD = C1.ID JOIN ZT_BUGRELATION SR ON A.ID = SR.BUG JOIN ZT_KEYWORDS KW ON SR.CUSTOMER = KW.ID '\
                    'WHERE C1. NAME = {version}  AND A.PRODUCT {project} AND A.FOUND IN ("PRODUCTIONRUN", "BVT") ORDER BY 编号'.format(version='"V'+version+'"',project=' in (15,23) ')
        #禅道链接
        con = pymysql.connect('112.74.115.12','root','Scxx_150906','zentao_qy',charset='utf8')
        cur = con.cursor()
        cur.execute(sql)
        data = cur.fetchall()
        cur = con.cursor()
        cur.execute('select t.desc from zt_build t where t.product {project} and t.name = {version}'.format(project=' in (15,23) ',version='"V'+version+'"'))
        comment = cur.fetchall()
        cur.close()
        con.close()
        if project == 24:
            title = '帕拉丁监管报表v'+version+'版本发布'
        else:
            title = '帕拉丁投资运营管理系统V'+version+'版本发布'
        content = "<div>各位好！</div>"\
                  "<div>"+title+"！升级资源请从以下路径获取：</div>"\
                  "<div>1、外网路径：ftp://112.74.115.12/ss/paladin/V\${VERSION}.zip"\
                  "<div style=\"color:red\">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;用户："+ftpuser+\
                  "<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;密码："+ftppwd+\
                  "<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;访问方式：Windows资源管理器访问上述路径，输入用户密码后，从远程ftp路径复制粘贴资源到本地；或使用ftp客户端连接（推荐方式）</div></div>"\
                  "<div>2、公司svn路径:http://192.168.72.99/svn/Repository/项目开发/版本管理/PLDOTC/${VERSION}+</div>"\
                  "<div>3、代码迁出路径：http://192.168.72.99/svn/Repository/项目开发/后台开发/代码/sc-paladin/branches/dveOtc/${VERSION}</div>"\
                  "${COMMENT}"\
                  "<div>-------------------------------------------------发布清单----------------------------------------------------</div>"\
                
        content = content.replace('${VERSION}',resourcename_dir)
        content = content + \
                  "<div><table border=\"1\" bordercolor=\"#000000\" cellpadding=\"2\" cellspacing=\"0\" style=\"font-size: 10pt; border-collapse:collapse;\" width=\"80%\">"\
                  "<tbody><tr>"\
                  "<td><div><b>版本号</b></div></td>"\
                  "<td><div><b>类型</b></div></td>"\
                  "<td><div><b>编号</b></div></td>"\
                  "<td><div><b>名称</b></div></td>"\
                  "</tr>"
        for i in range(len(data)):
            content = content + "<tr><td><div>" + str(data[i][0]) + "</div></td><td><div>" + str(data[i][1]) + "</div></td><td><div>" + str(data[i][2]) + "</div></td><td><div>" + str(data[i][3]) + "</div></td></tr>";
        content = content + "</tbody></table></div>"

        # 版本信息描述
        if comment[0][0] != '':
            comdiv = "<div>------------------------------------------------新版本特性---------------------------------------------------</div>"
            tmp = ""
            for com in comment[0][0].split(';'):
                tmp = tmp + "<li style=\"color:blue\">"+com+"</li>";
            tmp = "<ul>"+ tmp +"</ul>"
            content = content.replace("${COMMENT}",str(comdiv+tmp))
        else:
            content = content.replace("${COMMENT}",'')
        return title,content

class FTPTransfer():
    def __init__(self,url,user,pwd,encoding='gbk',directory=None,port='21'):
         try:
            self.ftp = ftplib.FTP(url)
            self.ftp.encoding = encoding
            self.ftp.set_pasv(False)
            self.ftp.login(user,pwd)
            self.remoteDir = directory
            # 切换远程ftp目录
            self.ftp.cwd(self.remoteDir)
            print('FTP登录成功...'+url)
         except Exception as ex:
            print('FTP登录失败!'+ex)


    def pushfile(self,filename):
        if not filename[0] == '~':
            print('FTP上传文件...'+filename)
            fp = open(filename, 'rb')
            self.ftp.storbinary('STOR ' + filename, fp, 1024)

    def pushdir(self,localdir):
        # 判断本地文件夹是否存在
        if not os.path.isdir(localdir):
            print('本地文件夹不存在:'+localdir)
            system.exit(1)

        # 重新创建远程文件夹
        dirname = localdir.split(os.sep)[-1]
        if dirname in self.ftp.nlst():
            self.__removedir(self.remoteDir+'/'+dirname)
        self.ftp.mkd(dirname)
        
        os.chdir(localdir)
        self.ftp.cwd(dirname)

        for f in os.listdir():
            if os.path.isdir(f):
                self.pushdir(f)
                os.chdir('..')
                self.ftp.cwd('..')
            else:
                self.pushfile(f)
        
    def __removedir(self,fulldir):
        print('删除文件夹...'+fulldir)
        self.ftp.cwd(fulldir)
        files = self.ftp.nlst(fulldir)
        # 先遍历删除文件夹下的所有文件/文件夹
        for f in files:
            try:
                self.ftp.cwd(f)#如果能切换进去，则说明是文件夹，再遍历
                self.ftp.cwd(fulldir)
                self.__removedir(f)
            except Exception as ex:
                self.ftp.delete(f)

        # 再回到上一级删除该空文件夹
        self.ftp.cwd('..')
        self.ftp.rmd(fulldir.split('/')[-1])

    def cd(self,dir):
        self.ftp.cwd(dir)
    
    def exit(self):
        self.ftp.quit()

def convertmailaddr(address):
    result = []
    if address:
        addrs = address.split(',')
        for addr in addrs:
            addr = addr.replace(' ','')
            result.append(re.search('<.*>',addr).group().replace('<','').replace('>',''))
    return ','.join(result)

if __name__ == '__main__':
    ew = EmailWriter('smtp.exmail.qq.com',993,user,passwd)
    title,content = ew.getversion(version)
    ew.writedraft(title,content,ew.getrecipient(To),ew.getrecipient(Cc))

    '''
    input('此操作会将【'+version+'】版本资源上传到发布路径!!!按任意键继续...')
    commitsvn = input('是否上传版本到内网SVN路径?(Y/N)')
    #commitsvn = sys.argv[1]
    
    assert commitsvn in ('y','Y','n','N'),'输入参数无效，请输入Y或N!'
    
    os.chdir(publishdir)
    
    # 先复制文件夹到内网发布路径
    if os.path.exists(resourcename_dir):
        shutil.rmtree(resourcename_dir)
    shutil.copytree(os.path.join(auto.archiveDir,version),resourcename_dir)
    
    # 再打成压缩包
    if os.path.exists(resourcename_arc):
        os.remove(resourcename_arc)
    winrar = r'C:\Program Files\WinRAR\WinRAR.exe'
    if os.path.exists(winrar):
        os.system(r'"C:\Program Files\WinRAR\WinRAR.exe" a {pak} {dir}'.format(pak=resourcename_arc,dir=resourcename_dir))
        os.system(r'"C:\Program Files\WinRAR\WinRAR.exe" c -z{file} {pak}'.format(file=os.path.join(auto.workDir,'paladin.version'),pak=resourcename_arc))
        print('版本压缩完成.')
    else:
        print('压缩软件不存在或路径错误!')

    print('上传版本到内网SVN...')
    if commitsvn.upper() == 'Y':
        # 上传版本文件夹
        print('正在提交SVN...')
        os.system('svn add '+resourcename_dir)
        os.system('svn commit -m "版本发布" '+resourcename_dir)
        # 写邮件
        ew = EmailWriter('smtp.exmail.qq.com',993,user,passwd)
        title,content = ew.getversion(project,version)
        ew.writedraft(title,content,convertmailaddr(To),convertmailaddr(Cc))
    else:
        print('取消上传SVN!')
    
    
    # 最后上传到外网ftp
    print('上传版本到外网FTP...')
    ftp_pub = FTPTransfer(ftpurl,ftpuser,ftppwd,'utf-8',publishdir_public)
    ftp_pub.pushfile(resourcename_arc)
    ftp_pub.pushdir(os.path.join(publishdir,resourcename_dir))
    print('FTP上传完成.')
    ftp_pub.exit()

    
    # 上传完删除本地的压缩包
    print('删除本地压缩包...')
    os.chdir(publishdir)
    if os.path.exists(resourcename_arc):
        os.remove(resourcename_arc)


    # *******************************************************************************************
    # 上传全量脚本
    print('上传全量脚本...')
    scriptroot = r'D:\Jenkins\workspace\帕拉丁系统自动构建\scxx-paladin\scxx-pal-base\数据库修改\\'
    ftpall = FTPTransfer(ftpurl,ftpuser,ftppwd,'utf-8',publishdir_public+'/0全量脚本')
    
    ftpall.pushdir(scriptroot+'场外脚本')
    ftpall.cd(ftpall.remoteDir)
    os.chdir(scriptroot)
    
    ftpall.pushdir(scriptroot+'监管报告')
    ftpall.cd(ftpall.remoteDir)
    os.chdir(scriptroot)
    
    ftpall.pushdir(scriptroot+'全系统共用')
    ftpall.cd(ftpall.remoteDir)
    os.chdir(scriptroot)
    
    ftpall.pushdir(scriptroot+'新报表')
    ftpall.exit()
    print('FTP上传完成.')
    # *******************************************************************************************
    
    print('操作完成.')
    input('按任意键退出...')'''
