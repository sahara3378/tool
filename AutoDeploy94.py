# -*- coding:gbk -*-
import logging
import sys, os
import signal
import platform
import subprocess
import shutil
import traceback
import hashlib

# ��������ģ�����ð�װ
# pip install cx_Oracle
# pip install pymysql
# pip install xlwt
import cx_Oracle, pymysql, xlwt

# ************************************************************* Start �������� Start *************************************************************
# ����·������
workDir = r'D:\AutoDeploy'  # ��ǰ����·��
archiveDir = r'D:\archives'  # ���·��
map_disk = 'J:\\' #ӳ���72.94���̷�

# ���ݿ��ṹԪ���ݵĵ��뷽ʽ��0��imp��������ִ�нű�
imp_type = 0
# ����������
dbconn_dev = r'pldotc_r/pldotc_r@192.168.72.110:1521/pdbdev'

last_database_version = -1

# *************************************************************** End �������� End **************************************************************

logger = logging.getLogger(__name__)


# ������־
def initLog():
    if os.path.exists('log-94.txt'):
        os.remove('log-94.txt')
    logger.setLevel(level=logging.INFO)
    handler = logging.FileHandler("log-94.txt")
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)

    logger.addHandler(handler)
    logger.addHandler(console)


# �����ļ���
def ReCreateDir(path):
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
        except Exception as ex:
            os.chdir(path)
            fp = open("txt.txt", 'w')
            fp.close()
            shutil.rmtree(path)
    os.makedirs(path)
    logger.info(path + ' created.')


# ת���ű�����gbk
# �����ύ�洢���� ��gbk����
# ��ͨ.sql��utf-8 ��BOM����
# �ű��а���word�ĵ���ֻ����
# addbegin ���ڽű���ʼ�Ķ���Ľű�
# addend ���ڽű�ĩβ�Ķ���Ľű�
# replacefeed �Ƿ�||chr(13)||�滻Ϊ���С�Kettle�����ݿ⵼���Ľű�����ѻ����滻Ϊ||chr(13)||���½ű�������sqlplus��֧��(SP2-0027)
def convertScript(filein, fileout, addbegin=None, addend=None, replacefeed=False):
    try:
        if '.pck' in filein or '.prc' in filein or '.plb' in filein:
            encode = 'gbk'
        elif '.sql' in filein or '.SQL' in filein:
            encode = 'utf-8'
        else:
            logger.info('coping file:' + filein + ' ' + fileout)
            shutil.copy(filein, fileout)
            return
        with open(filein, 'r', encoding=encode) as f1, open(fileout, 'w', encoding='gbk') as f2:
            if addbegin:
                f2.write(addbegin + '\n')
            for line in f1:
                if replacefeed:
                    #f2.write(line.replace('\'||chr(13)||\'', '\n'))
                    f2.write(line.replace('\\n', ' '))
                #����������12c����kettle������sql���\r�����½ű������쳣������ʱ����
                elif 'PLD_TASK_MANUAL_PARAM' in filein:
                    f2.write(line.replace('\\r', ' '))
                elif 'DPLD_TS_PROS_NODE_MAIL' in filein:
                    f2.write(line.replace('\\r', ' ').replace('\\n', ' '))
                else:
                    f2.write(line)
            if addend:
                if addend == True:  # Ĭ����־
                    if '.sql' in filein or '.SQL' in filein:
                        f2.write(
                            '\n\nINSERT INTO TS_PLD_UPGRADE_LOG (FTIME, F_VERSION, F_SCRIPT_NAME, REMARK) VALUES (SYSDATE, \'{version}\', \'{filename}\', NULL);\n'.format(
                                version=version,filename=os.path.basename(filein)))
                        f2.write('COMMIT;')
                else:  # �Զ�����־
                    f2.write(addend)
    except Exception as ex:
        logger.error('error converting file:' + filein)
        logger.error(ex)
        traceback.print_stack()
        sys.exit(1)


# ɨ���ļ��������нű�
# ��������˰����ű�include_files����ֻȡinclude_files�ļ��Ľű�
# ���δ���ð����ű�include_files����ֻ�ж���Щexclude_files�ű��ų��ˣ��޳���
# return (�ļ���,�ļ�����·��)
def getScripts(scan_dir, exclude_files=None, include_files=None):    
    file_result = []
    for root, dirs, files in os.walk(scan_dir):
        if '.svn' in dirs:
            dirs.remove('.svn')
        for file in files:
            if '.SQL' in file.upper() or '.PRC' in file.upper() or '.PCK' in file.upper():
                if include_files:
                    if isinstance(include_files, tuple):
                        if file in include_files:
                            file_result.append((file, os.path.join(root, file)))
                    elif file == include_files:
                        file_result.append((file, os.path.join(root, file)))
                else:
                    if isinstance(exclude_files, tuple):
                        # ɨ���ų����ļ��������������ȥ��
                        if file in exclude_files:
                            logger.info('�ų�... ' + os.path.join(root, file))
                        else:
                            file_result.append((file, os.path.join(root, file)))
                    elif file == exclude_files:
                        logger.info('�ų�... ' + os.path.join(root, file))
                    else:
                        file_result.append((file, os.path.join(root, file)))
    return file_result


# ��ȡ�ű�����
def GetDiffScript(ver,ver_l,compare_exp):
    logger.info(compare_exp)
    for compare_part in compare_exp.split('|'):
        root = compare_part.split('?')[0]
        output_dir = compare_part.split('?')[-1]
        output_dir_name = output_dir.replace('\\','-')

        if not os.path.exists('compare/%s-%s.txt'%(ver_l,output_dir_name)):
            logger.info('��ȡ�ϸ��汾�ű���Ϣ����')
            sys.exit(1)
        
        with open('compare/%s-%s.txt'%(ver_l,output_dir_name),'r') as fin,open('compare/%s-%s.txt' % (ver,output_dir_name),'w') as fout:
            pre_scripts = {}
            for pre_script in fin:
                key = pre_script.split(':')[0]
                value = pre_script.split(':')[1]
                pre_scripts[key] = value.replace('\n','')
            #logger.info(pre_scripts)
                
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir)
            os.makedirs(output_dir)

            childs = compare_part.split('?')[1].split(',')
            for child in childs:
                logger.info('�Ƚ��ļ��У�%s' % child)
                for r,y,fs in os.walk(os.path.join(root,child)):
                    for f in fs:
                        if '.SQL' in f.upper() or '.PRC' in f.upper() or '.PCK' in f.upper():
                            file = os.path.join(r,f)
                            file_md5 = get_md5(file)
                            fout.write(f+":"+file_md5+"\r")
                            if f not in list(pre_scripts.keys()):
                                logger.info('%s���%s�������ű�...%s'%(ver,ver_l,f))
                            else:
                                if file_md5 == pre_scripts[f]:#MD5�����򲻲���
                                    continue
                                else:
                                    logger.info('%s���%s�����½ű�...%s'%(ver,ver_l,f))
                            shutil.copy(file,output_dir)
                                
#��ȡ�ļ�MD5ֵ
def get_md5(file):
    with open(file, 'rb') as fp:
        data = fp.read()
    return hashlib.md5(data).hexdigest()   


# �����汾�ļ���
def CreateVerDir():
    logger.info('�����汾�ļ���...')
    ReCreateDir(os.path.join(workDir,'�ű�'))
    ReCreateDir(os.path.join(workDir,'�ű�','must'))
    ReCreateDir(os.path.join(workDir,'�ű�','option'))
    ReCreateDir(os.path.join(workDir,'�ű�','option_extension'))


# ����������>test/exp
def PrepareDb():
    logger.info('���¿������ṹԪ����...')
    conn = cx_Oracle.connect(dbconn_dev)
    cursor = conn.cursor()
    error_c = cursor.var(cx_Oracle.STRING)
    error_m = cursor.var(cx_Oracle.STRING)
    if version == version_l:
        logger.error('�汾�Ų�����ͬ')
        sys.exit(1)
    cursor.callproc('pa_pld_init.pr_��ȡ�汾��������', [version, version_l, 'PLDOTC', error_c, error_m])
    logger.info('ִ�����' + str(error_c.getvalue()) + ':' + str(error_m.getvalue()))

    logger.info('��տ�����PLD_SQL_LOG��')
    cursor.execute('TRUNCATE TABLE PLD_SQL_LOG')
    
    logger.info('�����������ṹԪ����(DMP)...')
    run_script = r'exp %s FILE=%s LOG=%s TABLES=PLD_INDEXES,PLD_PRIMARYS,PLD_SQL_LOG,PLD_TABLES,PLD_TABLE_COUT,PLD_TAB_COLUMNS,S_PLD_SQL,S_PLD_T_INDEXES,S_PLD_T_PRIMARYS,S_PLD_T_TABLES,S_PLD_T_TAB_COLUMNS,S_PLD_INDEX_EXPRESSIONS direct=y statistics=none' % (dbconn_dev, os.path.join(workDir, '�ű�', '1PLD_TABLES.DMP'),os.path.join(workDir, '�ű�', 'PLD_TABLES_EXP.LOG'))
    logger.info(run_script)
    re = subprocess.getstatusoutput(run_script)
    logger.info('�����������ṹԪ����(SQL)...')
    re1 = subprocess.getstatusoutput('sqlplus %s @%s %s' % (dbconn_dev, 'pld_data.sql', version))

    if re[0] == 0 and re1[0] == 0:
        logger.info('�����ɹ�!')
    else:
        logger.error('����ʧ��!' + re[1])
        sys.exit(1)


# ����ű�
def GenerateScript():
    logger.info('���������ű�...')

    convertScript(os.path.join(map_disk,'PLDRelease','0PLD_UPDATE.sql'),os.path.join(workDir,'�ű�','0PLD_UPDATE.SQL'),None,'\nQUIT;')
    convertScript(os.path.join(map_disk,'PLDRelease','2PA_PLD_UPDATE.pck'),os.path.join(workDir,'�ű�','2PA_PLD_UPDATE.SQL'),None,'\nQUIT;')

    #1 ���ô洢�����������ݰ汾
    #2 ����kettle�������ݽű�
    kettle = ('D:\Autodeploy\Kettle\����.bat ' + r'{workDir}\compare-script'.format(workDir=workDir)+' '+str(last_database_version)).replace('\\','/').format(version=version)
    #re = os.system(kettle)
    #kettle��ʱ�ᱨ�쳣���ೢ�Լ���
    for i in range(5):
        re = subprocess.getstatusoutput(kettle)
        logger.info(re[1])
        '''if re[0] == 0:
            logger.info('kettleִ�����!')
            break
        logger.error('kettleִ���쳣!')'''
        if not 'error' in re[1]:
            logger.info('kettleִ�����!')
            break
        logger.error('kettleִ���쳣!������...')
            
    
    
    # Ҫɨ��Ľű�Ŀ¼���Լ��ų���Ŀ¼�µ�ĳЩ�ļ�
    # ��ʽ ((�ű�·��1,�ų����ļ�,�������ļ�),(�ű�·��2,�ų����ļ�,�������ļ�),...)
    # ��: ((dir1,'excludefile.txt',None), (dir2,('excludefile1.sql','excludefile2.sql',None)), (dir3,None,('include1.sql','include2.sql')))
    script_musts = (
        (r'{workDir}\compare-script'.format(workDir=workDir),None,None),#�������߶Աȳ����ģ��Լ�kettle������
        (r'{project_script_dir}\����ű�\�汾�ű�\Ͷ��\{version}'.format(project_script_dir=project_script_dir,version=version),None,None),#Ͷ�ʰ汾�ű�
        (r'{project_script_dir}\����ű�\�汾�ű�\��Ӫ\{version}'.format(project_script_dir=project_script_dir,version=version),None,None),#��Ӫ�汾�ű�
        (r'{project_script_dir}\ȫϵͳ����\PUB'.format(project_script_dir=project_script_dir),None,'999-�����ݿ�ά���ֲ���ֱ����ɾ�ٲ�����ݽű�����.sql')#�������ִ�еĽű�
    )

    script_options = (
        (r'{project_dir}\doc\PLD_DB_Script'.format(project_dir=project_dir),'ע��.txt',None),#�洢���̣�ȫ������ÿ�ο�ֻ��������
    )
    
    script_options_extension = (
        (r'{project_dir}\doc\PLD_DB_Script_SS_EXTENSION'.format(project_dir=project_dir),'ע��.txt',None),#��չ�洢���̣����ֳ��ֹ�����
    )

    with open(os.path.join(workDir, '�ű�', 'V' + version + '.sql'), 'w', encoding='gbk') as file1:
        file1.write('set define off;\n')  # ʹ��sqlplus����&�ַ��᲻ʶ��
        with open(os.path.join(workDir,'�ű�','must','db.sql'),'w',encoding='gbk') as file2:
            # ����option
            for script in script_options:
                for f in getScripts(script[0], script[1], script[2]):
                    convertScript(f[1], os.path.join(workDir, '�ű�', 'option', f[0]),addend=True)
                    file1.write('prompt ����ִ��' + f[0] + '...\n')
                    file1.write('@@.' + os.sep + 'option' + os.sep + f[0] + ';\n')

            # ����option_extension
            for script in script_options_extension:
                for f in getScripts(script[0], script[1], script[2]):
                    convertScript(f[1], os.path.join(workDir, '�ű�', 'option_extension', f[0]),addend=True)

            # ����must
            for script in script_musts:
                for f in getScripts(script[0], script[1], script[2]):
                    if '.SQL' in f[0].upper() or '.PRC' in f[0].upper() or '.PCK' in f[0].upper():
                        if 'ETL_SQL' in f[0]:#��ʱ����
                            convertScript(f[1],os.path.join(workDir,'�ű�','must',f[0]),None,None,True)
                        else:
                            convertScript(f[1], os.path.join(workDir, '�ű�', 'must', f[0]),addend=True)
                        file1.write('prompt ����ִ��' + f[0] + '...\n')
                        file1.write('@@.' + os.sep + 'must' + os.sep + f[0] + ';\n')
                        file2.write('prompt ����ִ��' + f[0] + '...\n')
                        file2.write('@@' + f[0] + ';\n')

                    else:
                        convertScript(f[1],os.path.join(workDir,'�ű�',f[0]))
            file2.write(
            '\nINSERT INTO TS_PLD_UPGRADE_LOG VALUES(SYSDATE,\'VERSION\',\'' + 'db.sql' + '\',\'must�ű�,����must�ļ����µĽű�\');\n')
            file2.write('commit;\n')
            file2.write('exit;')
       
        file1.write(
            '\nINSERT INTO TS_PLD_UPGRADE_LOG VALUES(SYSDATE,\'VERSION\',\'' + 'v' + version + '.sql' + '\',\'�汾�ű�,����must��option�ļ����µĽű�\');\n')
        file1.write('commit;\n')
        file1.write('exit;')

    # ����汾��Դ,�������Ի�������������Ķ�����������
    logger.info('����汾��Դ...')
    ReCreateDir(os.path.join(archiveDir, 'V'+version))
    # ���������ű��ļ���
    shutil.copytree(os.path.join(workDir, '�ű�'), os.path.join(archiveDir, 'V'+version, '�ű�'))


# ɱ��tomcat����
def StopServer(tomcat_path):
    logger.info('�ر�tomcat...')
    if platform.system() == 'Windows':
        cmd = 'C:\\Windows\\System32\\wbem\\wmic.exe process where "CommandLine like \'%{tomcat_path}%\' and name=\'java.exe\'" get processid'.format(tomcat_path=os.path.join(tomcat_path,'conf').replace('\\','\\\\'))
        re = subprocess.getstatusoutput(cmd)
        if re[0] == 0:
            pid = re[1].split('\n')[2]
            if not pid:
                logger.warning('tomcatδ����')
            else:
                logger.info('tomcat���� %s' % pid)
                re = subprocess.getstatusoutput('taskkill /F /pid %s' % pid)
                if re[0] == 0:
                    logger.info('��ɱ��tomcat���� %s'%pid)
                else:
                    logger.error(re[1])            
    else:
        logger.error('linux��ʵ��...')


# ����Tomcat����
def StartServer(tomcat_dir):
    execu = os.path.join(tomcat_dir, 'bin', 'startup.bat' if platform.system() == 'Windows' else 'startup.sh')
    logger.info(execu)
    os.chdir(os.path.join(tomcat_dir, 'bin'))
    os.system('.\startup.bat')
    logger.info('������tomcat')
    

# �������Կ�>imp/test/sqlplus@
def ExecDb(dbconn):
    runDir = os.path.join(archiveDir, 'V'+version)
    os.chdir(os.path.join(runDir, '�ű�'))
    conn = cx_Oracle.connect(dbconn)
    cursor = conn.cursor()
    # �����ṹ
    logger.info('������Կ��ṹԪ����...')
    subprocess.getstatusoutput('sqlplus %s @%s' % (dbconn, os.path.join(runDir, '�ű�', '0PLD_UPDATE.SQL')))
    subprocess.getstatusoutput('sqlplus %s @%s' % (dbconn, os.path.join(runDir, '�ű�', '2PA_PLD_UPDATE.SQL')))

    if imp_type == 0:
        try:
            cursor.execute('TRUNCATE TABLE PLD_INDEXES')
            cursor.execute('TRUNCATE TABLE PLD_PRIMARYS')
            cursor.execute('TRUNCATE TABLE PLD_SQL_LOG')
            cursor.execute('TRUNCATE TABLE PLD_TABLES')
            cursor.execute('TRUNCATE TABLE PLD_TABLE_COUT')
            cursor.execute('TRUNCATE TABLE PLD_TAB_COLUMNS')
            
            cursor.execute('TRUNCATE TABLE S_PLD_SQL')
            cursor.execute('TRUNCATE TABLE S_PLD_T_INDEXES')
            cursor.execute('TRUNCATE TABLE S_PLD_T_PRIMARYS')
            cursor.execute('TRUNCATE TABLE S_PLD_T_TABLES')
            cursor.execute('TRUNCATE TABLE S_PLD_T_TAB_COLUMNS')
            cursor.execute('TRUNCATE TABLE S_PLD_INDEX_EXPRESSIONS')
        except:
            pass
        run_script = 'imp %s FILE=%s LOG=%s FROMUSER=%s TOUSER=%s IGNORE=Y commit=n buffer=65535' % (
            dbconn, os.path.join(runDir, '�ű�', '1PLD_TABLES.DMP'),
            os.path.join(runDir, '�ű�', '1PLD_TABLES_IMP.LOG'), dbconn_dev.split('/')[0], dbconn.split('/')[0])
        logger.info(run_script)
        subprocess.getstatusoutput(run_script)
    else:
        subprocess.getstatusoutput('sqlplus %s @%s' % (dbconn, os.path.join(runDir, '�ű�', 'PLD_TABLES.SQL')))

    # ���±�ṹ
    logger.info('���²��Կ��ṹ...')
    error_c = cursor.var(cx_Oracle.STRING)
    error_m = cursor.var(cx_Oracle.STRING)
    error_m2 = cursor.var(cx_Oracle.STRING)
    cursor.callproc('pa_pld_update.pr_update_test', [version, error_c, error_m, error_m2])
    logger.info('ִ�����:' + str(error_c.getvalue()) + str(error_m.getvalue()) + str(error_m2.getvalue()))
    if error_c.getvalue() not in ('0', '1'):
        logger.error('������ṹʧ��!')
        sys.exit(1)

    # ִ�������ű�
    logger.info('ִ�������ű�...')
    run_script = r'sqlplus %s @%s > %s' % (
        dbconn, os.path.join(runDir, '�ű�', 'v' + version + '.sql'), os.path.join(project_dir, 'dblog.txt'))
    logger.info(run_script)
    subprocess.getstatusoutput(run_script)

    # ���ø��»�����ű��洢����
    logger.info('���°汾��ű�...')
    conn = cx_Oracle.connect(dbconn)
    cursor = conn.cursor()
    error_c = cursor.var(cx_Oracle.STRING)
    error_m = cursor.var(cx_Oracle.STRING)
    #Todo 999999999�滻Ϊ���°汾�Ż�0
    cursor.callproc('pa_pld_update_dscript.pr_update_dscript',[0,0,error_c,error_m])
    if error_c.getvalue() != '0':
        logger.error('���°汾��ű�ʧ��!')
        sys.exit(1)
    logger.info('pr_update_dscriptִ�����'+str(error_c.getvalue())+':'+str(error_m.getvalue()))
    
    # ɾ����־�ļ�
    if os.path.exists('PLD_TABLES_EXP.LOG'):
        os.remove('PLD_TABLES_EXP.LOG')
    if os.path.exists('PLD_TABLES_IMP.LOG'):
        os.remove('PLD_TABLES_IMP.LOG')
    if os.path.exists('PLDRelease.log'):
        os.remove('PLDRelease.log')

    logger.info('���Կ������ɹ�')


# ����war����tomcatĿ¼
def Deploy():
    StopServer(tomcat_dir)
    
    runDir = os.path.join(archiveDir, 'V'+version)
    if not os.path.exists(runDir):
        os.makedirs(runDir)
    
    if os.path.exists(os.path.join(tomcat_dir, 'webapps', 'scxx-web')):
        logger.info('ɾ��tomcat-scxx-web...' + os.path.join(tomcat_dir, 'webapps', 'scxx-web'))
        os.system('rd /S /Q '+os.path.join(tomcat_dir, 'webapps', 'scxx-web'))
        #shutil.rmtree(os.path.join(tomcat_dir, 'webapps', 'scxx-web'))
    logger.info('�鵵war��...')
    shutil.copy(os.path.join(project_dir, 'scxx-web', 'target', 'scxx-web.war'), os.path.join(runDir, 'scxx-web.war'))
    logger.info('����war��...')
    shutil.copy(os.path.join(runDir, 'scxx-web.war'), os.path.join(tomcat_dir, 'webapps', 'scxx-web.war'))
    
    StartServer(tomcat_dir)


# ���ɰ汾��¼
def CreateExchange():
    runDir = os.path.join(archiveDir, 'V'+version)
    try:
        # 1�����ɰ汾��ṹ�ĵ�
        sql = 'SELECT T.F_VERSION_T, T.TABLE_NAME, T.FTYPE, T.COLUMN_NAME, T.DATA_TYPE_T, T.DATA_TYPE_L ' \
              'FROM PLD_UPDAE_INFO T WHERE T.F_VERSION_T = {ver} ORDER BY FTYPE, T.FSEQUENCE'.format(
            ver='\'' + version + '\'')
        con = cx_Oracle.connect(dbconn_dev)
        cur = con.cursor()
        cur.execute(sql)
        heads = []
        for i, j in enumerate(cur.description):
            heads.append(j[0])
        data = cur.fetchall()
        cur.close()
        con.close()

        with open(os.path.join(runDir, 'V' + version + '��ṹ���.txt'), 'w', encoding='gbk') as file:
            for head in heads:
                file.write(head.ljust(30, ' '))
            file.write('\n')
            for i in range(len(data)):
                for j in range(len(heads)):
                    file.write(('' if data[i][j] == None else data[i][j]).ljust(30, ' '))
                file.write('\n')
        logger.info('���ɱ�ṹ�ļ��ɹ�!')

        # 2�����ɷ����嵥
        sql = 'SELECT D.NAME AS �汾��, "����" AS ����, S.ID AS ���, S.TITLE AS ����, KW.NAME AS �ͻ�, D.DATE AS �������� ' \
              'FROM ZT_STORY S, ZT_BUILDSTORYBUG SB, ZT_BUILD D, ZT_STORYRELATION SR, ZT_KEYWORDS KW ' \
              'WHERE S.ID = SB.RELATEID AND SB.BUILD = D.ID AND S.ID = SR.STORY AND SR.CUSTOMER = KW.ID ' \
              'AND SB.TYPE = "story" AND S.PRODUCT IN (15,23) AND S.DELETED = "0" AND S.STATUS <> "closed" ' \
              'AND D.DELETED = "0" AND NOT D.NAME LIKE "PT%" AND D.NAME = {version}' \
              'UNION ALL ' \
              'SELECT C1. NAME �汾��, "BUG" ����, A.ID ���, A.TITLE ����, KW. NAME �ͻ�, C1.DATE �������� ' \
              'FROM ZT_BUG A LEFT JOIN ZT_BUILDSTORYBUG C ON A.ID = C.RELATEID LEFT JOIN ZT_BUILD C1 ON A.PRODUCT = C1.PRODUCT ' \
              'AND C.BUILD = C1.ID JOIN ZT_BUGRELATION SR ON A.ID = SR.BUG JOIN ZT_KEYWORDS KW ON SR.CUSTOMER = KW.ID ' \
              'WHERE C1. NAME = {version}  AND A.PRODUCT IN (15,23) AND A.FOUND IN ("PRODUCTIONRUN", "BVT") ORDER BY ���'.format(
            version='"V' + version + '"')
        # ��������
        con = pymysql.connect(host='112.74.115.12', user='root', password='Scxx_150906', database='zentao_qy', charset='utf8')
        cur = con.cursor()
        cur.execute(sql)
        heads = []
        for i, j in enumerate(cur.description):
            heads.append(j[0])
        data = cur.fetchall()
        cur.close()
        con.close()

        filename = os.path.join(runDir, 'V' + version + '��������.xls')
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet('�����嵥', cell_overwrite_ok=True)
        # ��ͷ
        for i, head in enumerate(heads):
            sheet1.write(0, i, head)

        # ����
        for row in range(1, len(data) + 1):
            for col in range(0, len(heads)):
                # �����ֶ�
                if col == 5:
                    datastyle = xlwt.XFStyle()
                    datastyle.num_format_str = 'yyyy-mm-dd'
                    sheet1.write(row, col, data[row - 1][col], datastyle)
                else:
                    sheet1.write(row, col, data[row - 1][col])

                # ���ú����п�
                sheet1.col(col).width = 256 * 10
                if col == 3:
                    sheet1.col(col).width = 256 * 100
        wbk.save(filename)
        logger.info('���ɷ����嵥excel�ɹ�!')

    except Exception as ex:
        logger.error('���ɰ汾��Ϣʧ��!' + ex)


# ���ִ�нű��Ƿ��б���
def CheckDbError():
    script_name = 'V%s.sql' % version
    with open(os.path.join(project_dir, 'dblog.txt'), 'r') as file:
        errorflag = False
        linestore = [''] * 10  # ��ǰȡ10�д�����־
        for line in file:
            for i in range(9):
                linestore[i] = linestore[i + 1]
            linestore[9] = line
            if '����ִ��' in line:
                # ����ִ��0-ETL_SQL.sql...
                script_name = line[4:][:-4]
            if 'ORA-' in line or 'SP2-' in line:
                errorflag = True
                logger.error('��⵽�ű�ִ�д���!��' + script_name + '��')
                logger.error("".join(linestore))
        if errorflag:
            sys.exit(1)
        else:
            logger.info('�ű���ִ�д���.')

def _read_config(file):
    keys = []
    with open(file,'r',encoding='utf8') as f:
        for l in f:
            if not l.startswith('#') and not l.strip()=='' and '=' in l:
                keys.append(l.split('=')[0].strip())
    return keys

# ��������Ƿ�ȱʧ
def CheckConfig(dbconn):

    # ��������ļ��Ƿ�ȱʧ����
    test_conf = _read_config('D:\\config\\sysConfig.properties')#Ŀǰд��sysConfig·�����Ժ���ʵ�ָ���tomcat��λ
    dev_conf = _read_config(os.path.join(project_dir,'scxx-web','src','main','resources','config','sysConfig.properties'))
    for c in dev_conf:
        if c not in test_conf:
            logger.error('Error�����Ի��������ļ�sysConfig.propertiesȱ�ٲ���[%s]����ע�⼰ʱ��ӣ�' % c)
            sys.exit(1)
    logger.info('�����ļ��������.')

    # ���ü�����ݵĴ洢����
    logger.info('���ü�����ݵĴ洢����...')
    conn = cx_Oracle.connect(dbconn)
    cursor = conn.cursor()
    error_c = cursor.var(cx_Oracle.STRING)
    error_m = cursor.var(cx_Oracle.STRING)
    cursor.callproc('pa_autotest.check_base_data_tran',[error_c,error_m])
    logger.info(error_m.getvalue())
    if error_c.getvalue() != '0':
        logger.error('���ݿ����ü������ʧ��!')
        sys.exit(1)
    else:
        logger.info('���ݿ����ü������.')

if __name__ == '__main__':
    os.chdir(workDir)
    initLog()

    if len(sys.argv) == 1:#���ֱ��ִ�иýű�,���������������õ�
        version = '1.8.8'#�汾��
        version_l = '1.8.7'#�ϸ��汾��
        project_dir = r'J:\trunk'#Դ��·��
        tomcat_dir = r'D:\app\apache-tomcat-8.5.73'#tomcat·��
        dbconn_test = r'paladin/1@192.168.72.110:1521/pdbtest'#���Կ�����
    elif len(sys.argv) == 7:
        type = sys.argv[1]
        version = sys.argv[2]
        version_l = sys.argv[3]
        project_dir = os.path.join(map_disk,sys.argv[4])
        tomcat_dir = sys.argv[5]
        dbconn_test = sys.argv[6]
    else:
        logger.error('��������')
        sys.exit(1)
    
    if type=='deploy':
        Deploy()
        sys.exit(0)
    elif type=='rundb':
        pass
    
    project_script_dir = os.path.join(project_dir,'doc','���ݿ��޸�')#���ݿ�ű�·��
    #����汾�ļ���
    CreateVerDir()
    #������ṹ
    PrepareDb()
    #��ȡ����ű�
    GetDiffScript(version,version_l,r'{project_script_dir}?ȫϵͳ����\PUB,����ű�\���ýű�\PUB_INT,����ű�\���ýű�\PUB_��ʱ����,����ű�\���ýű�\PUB_�����ӿ�?compare-script\���ݿ��޸�'.format(project_script_dir=project_script_dir))
    #����ű�
    GenerateScript()
    #ִ�нű�
    ExecDb(dbconn_test)
    #ֹͣtomcat,����war������tomcat
    Deploy()
    #���ɰ汾��¼
    CreateExchange()
    #���ű�ִ�б���
    CheckDbError()
    #��������Ƿ�ȱʧ
    CheckConfig(dbconn_test)
