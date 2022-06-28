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

######################################## �������� ##############################################################
version = '1.7.6'
project = auto.project
publishdir = auto.publishdir

#����FTP������Ϣ
ftpurl = 'x.x.x.x'
ftpuser = 'xx'
ftppwd = 'xx'
if project == 24:
    publishdir_public = '/ss/paladin/��ܱ���汾'
else:
    publishdir_public = '/ss/paladin'

if project == 24:
    publishdir_public = '/ss/paladin/��ܱ���汾'
    publishdir_private = 'http://192.168.72.99/svn/Repository/��Ŀ����/�����汾/��ܱ���'
    resourcename_dir = time.strftime('%Y%m%d-',time.localtime())+'v'+version
else:
    publishdir_public = '/ss/paladin'
    publishdir_private = 'http://192.168.72.99/svn/Repository/��Ŀ����/�����汾'
    resourcename_dir = 'v'+version #���м�

resourcename_arc = resourcename_dir + '.zip'

#������Ϣ
user = 'xx' #������
passwd = 'xx' #����������
To = ('ʵʩ�������ڣ�','ʵʩ����������')#�ռ���-��ȡ��������
Cc = ('������������','������������','������������')#������-��ȡ��������

################################################################################################################


class EmailWriter():
    def __init__(self,host,port,user,pwd):
        try:
            self.user=user
            self.conn = imaplib.IMAP4_SSL(host, port)
            print(user)
            print(pwd)
            self.conn.login(self.user, pwd)
            print('�ʼ���ʼ���ɹ�.')
            self.initialized = True
        except Exception as ex:
            print('�ʼ���ʼ������!'+ex)
            self.initialized = False
            
    # д�ʼ��ݸ�
    def writedraft(self,title,content,rec,cc=None):
        print('���ڱ�д�ʼ��ݸ�...')
        if self.initialized:
            try:
                #print(conn.select('Drafts')[1][0])#��ѯ�ݸ��ļ����ж�������¼
                message = MIMEText(content, 'html', 'utf-8')
                message['From'] = self.user#������
                message['To'] =  rec#�ռ���
                if cc:
                    message['Cc'] =  cc#������
                message['Subject'] = Header(title, 'utf-8')
                self.conn.append('Drafts','',imaplib.Time2Internaldate(time.time()),message.as_bytes())
            except Exception as ex:
                print(ex)
            print('�ʼ��ݸ��д���,���¼���䡾'+self.user+'�����/�����ʼ�.')
        else:
            print('�ʼ�����δ��ʼ��!')


    # ���ݲ��Ż�ȡ�������ռ���
    def getrecipient(self,dept):
        depts = '\'' +','.join(dept).replace(',','\',\'') + '\''
        sql = 'select group_concat(u.email order by u.id) from zt_user u join zt_dept d on u.dept=d.id where d.name in({dept}) and u.deleted=\'0\''.format(dept=depts)
        #��������
        con = pymysql.connect('112.74.115.12','root','Scxx_150906','zentao_qy',charset='utf8')
        cur = con.cursor()
        cur.execute(sql)
        data = cur.fetchall()
        cur.close()
        con.close()
        print(data[0][0])
        return data[0][0]

    # ��ѯ�������ݿ⣬��ȡ�汾�����嵥
    def getversion(self,version):
        sql = 'SELECT D.NAME AS �汾��, "����" AS ����, S.ID AS ���, S.TITLE AS ���� '\
                    'FROM ZT_STORY S, ZT_BUILDSTORYBUG SB, ZT_BUILD D, ZT_STORYRELATION SR, ZT_KEYWORDS KW '\
                    'WHERE S.ID = SB.RELATEID AND SB.BUILD = D.ID AND S.ID = SR.STORY AND SR.CUSTOMER = KW.ID '\
                    'AND SB.TYPE = "story" AND S.PRODUCT {project} AND S.DELETED = "0" AND S.STATUS <> "closed" '\
                    'AND D.DELETED = "0" AND NOT D.NAME LIKE "PT%" AND D.NAME = {version}'\
                    'UNION ALL '\
                    'SELECT C1. NAME �汾��, "BUG" ����, A.ID ���, A.TITLE ���� '\
                    'FROM ZT_BUG A LEFT JOIN ZT_BUILDSTORYBUG C ON A.ID = C.RELATEID LEFT JOIN ZT_BUILD C1 ON A.PRODUCT = C1.PRODUCT '\
                    'AND C.BUILD = C1.ID JOIN ZT_BUGRELATION SR ON A.ID = SR.BUG JOIN ZT_KEYWORDS KW ON SR.CUSTOMER = KW.ID '\
                    'WHERE C1. NAME = {version}  AND A.PRODUCT {project} AND A.FOUND IN ("PRODUCTIONRUN", "BVT") ORDER BY ���'.format(version='"V'+version+'"',project=' in (15,23) ')
        #��������
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
            title = '��������ܱ���v'+version+'�汾����'
        else:
            title = '������Ͷ����Ӫ����ϵͳV'+version+'�汾����'
        content = "<div>��λ�ã�</div>"\
                  "<div>"+title+"��������Դ�������·����ȡ��</div>"\
                  "<div>1������·����ftp://112.74.115.12/ss/paladin/V\${VERSION}.zip"\
                  "<div style=\"color:red\">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;�û���"+ftpuser+\
                  "<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;���룺"+ftppwd+\
                  "<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;���ʷ�ʽ��Windows��Դ��������������·���������û�����󣬴�Զ��ftp·������ճ����Դ�����أ���ʹ��ftp�ͻ������ӣ��Ƽ���ʽ��</div></div>"\
                  "<div>2����˾svn·��:http://192.168.72.99/svn/Repository/��Ŀ����/�汾����/PLDOTC/${VERSION}+</div>"\
                  "<div>3������Ǩ��·����http://192.168.72.99/svn/Repository/��Ŀ����/��̨����/����/sc-paladin/branches/dveOtc/${VERSION}</div>"\
                  "${COMMENT}"\
                  "<div>-------------------------------------------------�����嵥----------------------------------------------------</div>"\
                
        content = content.replace('${VERSION}',resourcename_dir)
        content = content + \
                  "<div><table border=\"1\" bordercolor=\"#000000\" cellpadding=\"2\" cellspacing=\"0\" style=\"font-size: 10pt; border-collapse:collapse;\" width=\"80%\">"\
                  "<tbody><tr>"\
                  "<td><div><b>�汾��</b></div></td>"\
                  "<td><div><b>����</b></div></td>"\
                  "<td><div><b>���</b></div></td>"\
                  "<td><div><b>����</b></div></td>"\
                  "</tr>"
        for i in range(len(data)):
            content = content + "<tr><td><div>" + str(data[i][0]) + "</div></td><td><div>" + str(data[i][1]) + "</div></td><td><div>" + str(data[i][2]) + "</div></td><td><div>" + str(data[i][3]) + "</div></td></tr>";
        content = content + "</tbody></table></div>"

        # �汾��Ϣ����
        if comment[0][0] != '':
            comdiv = "<div>------------------------------------------------�°汾����---------------------------------------------------</div>"
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
            # �л�Զ��ftpĿ¼
            self.ftp.cwd(self.remoteDir)
            print('FTP��¼�ɹ�...'+url)
         except Exception as ex:
            print('FTP��¼ʧ��!'+ex)


    def pushfile(self,filename):
        if not filename[0] == '~':
            print('FTP�ϴ��ļ�...'+filename)
            fp = open(filename, 'rb')
            self.ftp.storbinary('STOR ' + filename, fp, 1024)

    def pushdir(self,localdir):
        # �жϱ����ļ����Ƿ����
        if not os.path.isdir(localdir):
            print('�����ļ��в�����:'+localdir)
            system.exit(1)

        # ���´���Զ���ļ���
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
        print('ɾ���ļ���...'+fulldir)
        self.ftp.cwd(fulldir)
        files = self.ftp.nlst(fulldir)
        # �ȱ���ɾ���ļ����µ������ļ�/�ļ���
        for f in files:
            try:
                self.ftp.cwd(f)#������л���ȥ����˵�����ļ��У��ٱ���
                self.ftp.cwd(fulldir)
                self.__removedir(f)
            except Exception as ex:
                self.ftp.delete(f)

        # �ٻص���һ��ɾ���ÿ��ļ���
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
    input('�˲����Ὣ��'+version+'���汾��Դ�ϴ�������·��!!!�����������...')
    commitsvn = input('�Ƿ��ϴ��汾������SVN·��?(Y/N)')
    #commitsvn = sys.argv[1]
    
    assert commitsvn in ('y','Y','n','N'),'���������Ч��������Y��N!'
    
    os.chdir(publishdir)
    
    # �ȸ����ļ��е���������·��
    if os.path.exists(resourcename_dir):
        shutil.rmtree(resourcename_dir)
    shutil.copytree(os.path.join(auto.archiveDir,version),resourcename_dir)
    
    # �ٴ��ѹ����
    if os.path.exists(resourcename_arc):
        os.remove(resourcename_arc)
    winrar = r'C:\Program Files\WinRAR\WinRAR.exe'
    if os.path.exists(winrar):
        os.system(r'"C:\Program Files\WinRAR\WinRAR.exe" a {pak} {dir}'.format(pak=resourcename_arc,dir=resourcename_dir))
        os.system(r'"C:\Program Files\WinRAR\WinRAR.exe" c -z{file} {pak}'.format(file=os.path.join(auto.workDir,'paladin.version'),pak=resourcename_arc))
        print('�汾ѹ�����.')
    else:
        print('ѹ����������ڻ�·������!')

    print('�ϴ��汾������SVN...')
    if commitsvn.upper() == 'Y':
        # �ϴ��汾�ļ���
        print('�����ύSVN...')
        os.system('svn add '+resourcename_dir)
        os.system('svn commit -m "�汾����" '+resourcename_dir)
        # д�ʼ�
        ew = EmailWriter('smtp.exmail.qq.com',993,user,passwd)
        title,content = ew.getversion(project,version)
        ew.writedraft(title,content,convertmailaddr(To),convertmailaddr(Cc))
    else:
        print('ȡ���ϴ�SVN!')
    
    
    # ����ϴ�������ftp
    print('�ϴ��汾������FTP...')
    ftp_pub = FTPTransfer(ftpurl,ftpuser,ftppwd,'utf-8',publishdir_public)
    ftp_pub.pushfile(resourcename_arc)
    ftp_pub.pushdir(os.path.join(publishdir,resourcename_dir))
    print('FTP�ϴ����.')
    ftp_pub.exit()

    
    # �ϴ���ɾ�����ص�ѹ����
    print('ɾ������ѹ����...')
    os.chdir(publishdir)
    if os.path.exists(resourcename_arc):
        os.remove(resourcename_arc)


    # *******************************************************************************************
    # �ϴ�ȫ���ű�
    print('�ϴ�ȫ���ű�...')
    scriptroot = r'D:\Jenkins\workspace\������ϵͳ�Զ�����\scxx-paladin\scxx-pal-base\���ݿ��޸�\\'
    ftpall = FTPTransfer(ftpurl,ftpuser,ftppwd,'utf-8',publishdir_public+'/0ȫ���ű�')
    
    ftpall.pushdir(scriptroot+'����ű�')
    ftpall.cd(ftpall.remoteDir)
    os.chdir(scriptroot)
    
    ftpall.pushdir(scriptroot+'��ܱ���')
    ftpall.cd(ftpall.remoteDir)
    os.chdir(scriptroot)
    
    ftpall.pushdir(scriptroot+'ȫϵͳ����')
    ftpall.cd(ftpall.remoteDir)
    os.chdir(scriptroot)
    
    ftpall.pushdir(scriptroot+'�±���')
    ftpall.exit()
    print('FTP�ϴ����.')
    # *******************************************************************************************
    
    print('�������.')
    input('��������˳�...')'''
