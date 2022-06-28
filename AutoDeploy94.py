# -*- coding:gbk -*-
import logging
import sys, os
import signal
import platform
import subprocess
import shutil
import traceback
import hashlib

# 以下三个模块需用安装
# pip install cx_Oracle
# pip install pymysql
# pip install xlwt
import cx_Oracle, pymysql, xlwt

# ************************************************************* Start 配置区域 Start *************************************************************
# 基础路径配置
workDir = r'D:\AutoDeploy'  # 当前工作路径
archiveDir = r'D:\archives'  # 打包路径
map_disk = 'J:\\' #映射的72.94的盘符

# 数据库表结构元数据的导入方式，0是imp，其它是执行脚本
imp_type = 0
# 开发库链接
dbconn_dev = r'pldotc_r/pldotc_r@192.168.72.110:1521/pdbdev'

last_database_version = -1

# *************************************************************** End 配置区域 End **************************************************************

logger = logging.getLogger(__name__)


# 配置日志
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


# 创建文件夹
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


# 转换脚本编码gbk
# 开发提交存储过程 用gbk编码
# 普通.sql用utf-8 无BOM编码
# 脚本中包含word文档，只拷贝
# addbegin 放在脚本开始的多余的脚本
# addend 放在脚本末尾的多余的脚本
# replacefeed 是否将||chr(13)||替换为换行。Kettle从数据库导出的脚本，会把换行替换为||chr(13)||导致脚本过长，sqlplus不支持(SP2-0027)
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
                #开发库升级12c后，用kettle导出的sql会带\r，导致脚本内容异常，先临时处理
                elif 'PLD_TASK_MANUAL_PARAM' in filein:
                    f2.write(line.replace('\\r', ' '))
                elif 'DPLD_TS_PROS_NODE_MAIL' in filein:
                    f2.write(line.replace('\\r', ' ').replace('\\n', ' '))
                else:
                    f2.write(line)
            if addend:
                if addend == True:  # 默认日志
                    if '.sql' in filein or '.SQL' in filein:
                        f2.write(
                            '\n\nINSERT INTO TS_PLD_UPGRADE_LOG (FTIME, F_VERSION, F_SCRIPT_NAME, REMARK) VALUES (SYSDATE, \'{version}\', \'{filename}\', NULL);\n'.format(
                                version=version,filename=os.path.basename(filein)))
                        f2.write('COMMIT;')
                else:  # 自定义日志
                    f2.write(addend)
    except Exception as ex:
        logger.error('error converting file:' + filein)
        logger.error(ex)
        traceback.print_stack()
        sys.exit(1)


# 扫描文件夹下所有脚本
# 如果设置了包含脚本include_files，就只取include_files文件的脚本
# 如果未设置包含脚本include_files，则只判断哪些exclude_files脚本排除了，剔除掉
# return (文件名,文件完整路径)
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
                        # 扫描排除的文件，如果在其中则去掉
                        if file in exclude_files:
                            logger.info('排除... ' + os.path.join(root, file))
                        else:
                            file_result.append((file, os.path.join(root, file)))
                    elif file == exclude_files:
                        logger.info('排除... ' + os.path.join(root, file))
                    else:
                        file_result.append((file, os.path.join(root, file)))
    return file_result


# 获取脚本差异
def GetDiffScript(ver,ver_l,compare_exp):
    logger.info(compare_exp)
    for compare_part in compare_exp.split('|'):
        root = compare_part.split('?')[0]
        output_dir = compare_part.split('?')[-1]
        output_dir_name = output_dir.replace('\\','-')

        if not os.path.exists('compare/%s-%s.txt'%(ver_l,output_dir_name)):
            logger.info('获取上个版本脚本信息有误！')
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
                logger.info('比较文件夹：%s' % child)
                for r,y,fs in os.walk(os.path.join(root,child)):
                    for f in fs:
                        if '.SQL' in f.upper() or '.PRC' in f.upper() or '.PCK' in f.upper():
                            file = os.path.join(r,f)
                            file_md5 = get_md5(file)
                            fout.write(f+":"+file_md5+"\r")
                            if f not in list(pre_scripts.keys()):
                                logger.info('%s相比%s，新增脚本...%s'%(ver,ver_l,f))
                            else:
                                if file_md5 == pre_scripts[f]:#MD5不变则不操作
                                    continue
                                else:
                                    logger.info('%s相比%s，更新脚本...%s'%(ver,ver_l,f))
                            shutil.copy(file,output_dir)
                                
#获取文件MD5值
def get_md5(file):
    with open(file, 'rb') as fp:
        data = fp.read()
    return hashlib.md5(data).hexdigest()   


# 创建版本文件夹
def CreateVerDir():
    logger.info('创建版本文件夹...')
    ReCreateDir(os.path.join(workDir,'脚本'))
    ReCreateDir(os.path.join(workDir,'脚本','must'))
    ReCreateDir(os.path.join(workDir,'脚本','option'))
    ReCreateDir(os.path.join(workDir,'脚本','option_extension'))


# 导出开发库>test/exp
def PrepareDb():
    logger.info('更新开发库表结构元数据...')
    conn = cx_Oracle.connect(dbconn_dev)
    cursor = conn.cursor()
    error_c = cursor.var(cx_Oracle.STRING)
    error_m = cursor.var(cx_Oracle.STRING)
    if version == version_l:
        logger.error('版本号不能相同')
        sys.exit(1)
    cursor.callproc('pa_pld_init.pr_获取版本更新数据', [version, version_l, 'PLDOTC', error_c, error_m])
    logger.info('执行完成' + str(error_c.getvalue()) + ':' + str(error_m.getvalue()))

    logger.info('清空开发库PLD_SQL_LOG表')
    cursor.execute('TRUNCATE TABLE PLD_SQL_LOG')
    
    logger.info('导出开发库表结构元数据(DMP)...')
    run_script = r'exp %s FILE=%s LOG=%s TABLES=PLD_INDEXES,PLD_PRIMARYS,PLD_SQL_LOG,PLD_TABLES,PLD_TABLE_COUT,PLD_TAB_COLUMNS,S_PLD_SQL,S_PLD_T_INDEXES,S_PLD_T_PRIMARYS,S_PLD_T_TABLES,S_PLD_T_TAB_COLUMNS,S_PLD_INDEX_EXPRESSIONS direct=y statistics=none' % (dbconn_dev, os.path.join(workDir, '脚本', '1PLD_TABLES.DMP'),os.path.join(workDir, '脚本', 'PLD_TABLES_EXP.LOG'))
    logger.info(run_script)
    re = subprocess.getstatusoutput(run_script)
    logger.info('导出开发库表结构元数据(SQL)...')
    re1 = subprocess.getstatusoutput('sqlplus %s @%s %s' % (dbconn_dev, 'pld_data.sql', version))

    if re[0] == 0 and re1[0] == 0:
        logger.info('导出成功!')
    else:
        logger.error('导出失败!' + re[1])
        sys.exit(1)


# 整理脚本
def GenerateScript():
    logger.info('整理升级脚本...')

    convertScript(os.path.join(map_disk,'PLDRelease','0PLD_UPDATE.sql'),os.path.join(workDir,'脚本','0PLD_UPDATE.SQL'),None,'\nQUIT;')
    convertScript(os.path.join(map_disk,'PLDRelease','2PA_PLD_UPDATE.pck'),os.path.join(workDir,'脚本','2PA_PLD_UPDATE.SQL'),None,'\nQUIT;')

    #1 调用存储过程生成数据版本
    #2 调用kettle导出数据脚本
    kettle = ('D:\Autodeploy\Kettle\运行.bat ' + r'{workDir}\compare-script'.format(workDir=workDir)+' '+str(last_database_version)).replace('\\','/').format(version=version)
    #re = os.system(kettle)
    #kettle有时会报异常，多尝试几次
    for i in range(5):
        re = subprocess.getstatusoutput(kettle)
        logger.info(re[1])
        '''if re[0] == 0:
            logger.info('kettle执行完成!')
            break
        logger.error('kettle执行异常!')'''
        if not 'error' in re[1]:
            logger.info('kettle执行完成!')
            break
        logger.error('kettle执行异常!重试中...')
            
    
    
    # 要扫描的脚本目录，以及排除该目录下的某些文件
    # 格式 ((脚本路径1,排除的文件,包含的文件),(脚本路径2,排除的文件,包含的文件),...)
    # 如: ((dir1,'excludefile.txt',None), (dir2,('excludefile1.sql','excludefile2.sql',None)), (dir3,None,('include1.sql','include2.sql')))
    script_musts = (
        (r'{workDir}\compare-script'.format(workDir=workDir),None,None),#开发工具对比出来的，以及kettle导出的
        (r'{project_script_dir}\场外脚本\版本脚本\投资\{version}'.format(project_script_dir=project_script_dir,version=version),None,None),#投资版本脚本
        (r'{project_script_dir}\场外脚本\版本脚本\运营\{version}'.format(project_script_dir=project_script_dir,version=version),None,None),#运营版本脚本
        (r'{project_script_dir}\全系统共用\PUB'.format(project_script_dir=project_script_dir),None,'999-在数据库维护又不能直接先删再插的数据脚本更新.sql')#放在最后执行的脚本
    )

    script_options = (
        (r'{project_dir}\doc\PLD_DB_Script'.format(project_dir=project_dir),'注意.txt',None),#存储过程，全量发，每次可只更新最新
    )
    
    script_options_extension = (
        (r'{project_dir}\doc\PLD_DB_Script_SS_EXTENSION'.format(project_dir=project_dir),'注意.txt',None),#扩展存储过程，需现场手工处理
    )

    with open(os.path.join(workDir, '脚本', 'V' + version + '.sql'), 'w', encoding='gbk') as file1:
        file1.write('set define off;\n')  # 使用sqlplus遇到&字符会不识别
        with open(os.path.join(workDir,'脚本','must','db.sql'),'w',encoding='gbk') as file2:
            # 拷贝option
            for script in script_options:
                for f in getScripts(script[0], script[1], script[2]):
                    convertScript(f[1], os.path.join(workDir, '脚本', 'option', f[0]),addend=True)
                    file1.write('prompt 正在执行' + f[0] + '...\n')
                    file1.write('@@.' + os.sep + 'option' + os.sep + f[0] + ';\n')

            # 拷贝option_extension
            for script in script_options_extension:
                for f in getScripts(script[0], script[1], script[2]):
                    convertScript(f[1], os.path.join(workDir, '脚本', 'option_extension', f[0]),addend=True)

            # 拷贝must
            for script in script_musts:
                for f in getScripts(script[0], script[1], script[2]):
                    if '.SQL' in f[0].upper() or '.PRC' in f[0].upper() or '.PCK' in f[0].upper():
                        if 'ETL_SQL' in f[0]:#临时处理
                            convertScript(f[1],os.path.join(workDir,'脚本','must',f[0]),None,None,True)
                        else:
                            convertScript(f[1], os.path.join(workDir, '脚本', 'must', f[0]),addend=True)
                        file1.write('prompt 正在执行' + f[0] + '...\n')
                        file1.write('@@.' + os.sep + 'must' + os.sep + f[0] + ';\n')
                        file2.write('prompt 正在执行' + f[0] + '...\n')
                        file2.write('@@' + f[0] + ';\n')

                    else:
                        convertScript(f[1],os.path.join(workDir,'脚本',f[0]))
            file2.write(
            '\nINSERT INTO TS_PLD_UPGRADE_LOG VALUES(SYSDATE,\'VERSION\',\'' + 'db.sql' + '\',\'must脚本,包含must文件夹下的脚本\');\n')
            file2.write('commit;\n')
            file2.write('exit;')
       
        file1.write(
            '\nINSERT INTO TS_PLD_UPGRADE_LOG VALUES(SYSDATE,\'VERSION\',\'' + 'v' + version + '.sql' + '\',\'版本脚本,包含must及option文件夹下的脚本\');\n')
        file1.write('commit;\n')
        file1.write('exit;')

    # 整理版本资源,整个测试环境基于这下面的东西进行升级
    logger.info('整理版本资源...')
    ReCreateDir(os.path.join(archiveDir, 'V'+version))
    # 复制整个脚本文件夹
    shutil.copytree(os.path.join(workDir, '脚本'), os.path.join(archiveDir, 'V'+version, '脚本'))


# 杀死tomcat进程
def StopServer(tomcat_path):
    logger.info('关闭tomcat...')
    if platform.system() == 'Windows':
        cmd = 'C:\\Windows\\System32\\wbem\\wmic.exe process where "CommandLine like \'%{tomcat_path}%\' and name=\'java.exe\'" get processid'.format(tomcat_path=os.path.join(tomcat_path,'conf').replace('\\','\\\\'))
        re = subprocess.getstatusoutput(cmd)
        if re[0] == 0:
            pid = re[1].split('\n')[2]
            if not pid:
                logger.warning('tomcat未运行')
            else:
                logger.info('tomcat进程 %s' % pid)
                re = subprocess.getstatusoutput('taskkill /F /pid %s' % pid)
                if re[0] == 0:
                    logger.info('已杀掉tomcat进程 %s'%pid)
                else:
                    logger.error(re[1])            
    else:
        logger.error('linux待实现...')


# 启动Tomcat进程
def StartServer(tomcat_dir):
    execu = os.path.join(tomcat_dir, 'bin', 'startup.bat' if platform.system() == 'Windows' else 'startup.sh')
    logger.info(execu)
    os.chdir(os.path.join(tomcat_dir, 'bin'))
    os.system('.\startup.bat')
    logger.info('已启动tomcat')
    

# 升级测试库>imp/test/sqlplus@
def ExecDb(dbconn):
    runDir = os.path.join(archiveDir, 'V'+version)
    os.chdir(os.path.join(runDir, '脚本'))
    conn = cx_Oracle.connect(dbconn)
    cursor = conn.cursor()
    # 导入表结构
    logger.info('导入测试库表结构元数据...')
    subprocess.getstatusoutput('sqlplus %s @%s' % (dbconn, os.path.join(runDir, '脚本', '0PLD_UPDATE.SQL')))
    subprocess.getstatusoutput('sqlplus %s @%s' % (dbconn, os.path.join(runDir, '脚本', '2PA_PLD_UPDATE.SQL')))

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
            dbconn, os.path.join(runDir, '脚本', '1PLD_TABLES.DMP'),
            os.path.join(runDir, '脚本', '1PLD_TABLES_IMP.LOG'), dbconn_dev.split('/')[0], dbconn.split('/')[0])
        logger.info(run_script)
        subprocess.getstatusoutput(run_script)
    else:
        subprocess.getstatusoutput('sqlplus %s @%s' % (dbconn, os.path.join(runDir, '脚本', 'PLD_TABLES.SQL')))

    # 更新表结构
    logger.info('更新测试库表结构...')
    error_c = cursor.var(cx_Oracle.STRING)
    error_m = cursor.var(cx_Oracle.STRING)
    error_m2 = cursor.var(cx_Oracle.STRING)
    cursor.callproc('pa_pld_update.pr_update_test', [version, error_c, error_m, error_m2])
    logger.info('执行完成:' + str(error_c.getvalue()) + str(error_m.getvalue()) + str(error_m2.getvalue()))
    if error_c.getvalue() not in ('0', '1'):
        logger.error('升级表结构失败!')
        sys.exit(1)

    # 执行升级脚本
    logger.info('执行升级脚本...')
    run_script = r'sqlplus %s @%s > %s' % (
        dbconn, os.path.join(runDir, '脚本', 'v' + version + '.sql'), os.path.join(project_dir, 'dblog.txt'))
    logger.info(run_script)
    subprocess.getstatusoutput(run_script)

    # 调用更新基础库脚本存储过程
    logger.info('更新版本库脚本...')
    conn = cx_Oracle.connect(dbconn)
    cursor = conn.cursor()
    error_c = cursor.var(cx_Oracle.STRING)
    error_m = cursor.var(cx_Oracle.STRING)
    #Todo 999999999替换为最新版本号或0
    cursor.callproc('pa_pld_update_dscript.pr_update_dscript',[0,0,error_c,error_m])
    if error_c.getvalue() != '0':
        logger.error('更新版本库脚本失败!')
        sys.exit(1)
    logger.info('pr_update_dscript执行完成'+str(error_c.getvalue())+':'+str(error_m.getvalue()))
    
    # 删除日志文件
    if os.path.exists('PLD_TABLES_EXP.LOG'):
        os.remove('PLD_TABLES_EXP.LOG')
    if os.path.exists('PLD_TABLES_IMP.LOG'):
        os.remove('PLD_TABLES_IMP.LOG')
    if os.path.exists('PLDRelease.log'):
        os.remove('PLDRelease.log')

    logger.info('测试库升级成功')


# 部署war包到tomcat目录
def Deploy():
    StopServer(tomcat_dir)
    
    runDir = os.path.join(archiveDir, 'V'+version)
    if not os.path.exists(runDir):
        os.makedirs(runDir)
    
    if os.path.exists(os.path.join(tomcat_dir, 'webapps', 'scxx-web')):
        logger.info('删除tomcat-scxx-web...' + os.path.join(tomcat_dir, 'webapps', 'scxx-web'))
        os.system('rd /S /Q '+os.path.join(tomcat_dir, 'webapps', 'scxx-web'))
        #shutil.rmtree(os.path.join(tomcat_dir, 'webapps', 'scxx-web'))
    logger.info('归档war包...')
    shutil.copy(os.path.join(project_dir, 'scxx-web', 'target', 'scxx-web.war'), os.path.join(runDir, 'scxx-web.war'))
    logger.info('部署war包...')
    shutil.copy(os.path.join(runDir, 'scxx-web.war'), os.path.join(tomcat_dir, 'webapps', 'scxx-web.war'))
    
    StartServer(tomcat_dir)


# 生成版本记录
def CreateExchange():
    runDir = os.path.join(archiveDir, 'V'+version)
    try:
        # 1、生成版本表结构文档
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

        with open(os.path.join(runDir, 'V' + version + '表结构变更.txt'), 'w', encoding='gbk') as file:
            for head in heads:
                file.write(head.ljust(30, ' '))
            file.write('\n')
            for i in range(len(data)):
                for j in range(len(heads)):
                    file.write(('' if data[i][j] == None else data[i][j]).ljust(30, ' '))
                file.write('\n')
        logger.info('生成表结构文件成功!')

        # 2、生成发布清单
        sql = 'SELECT D.NAME AS 版本号, "需求" AS 类型, S.ID AS 编号, S.TITLE AS 名称, KW.NAME AS 客户, D.DATE AS 发布日期 ' \
              'FROM ZT_STORY S, ZT_BUILDSTORYBUG SB, ZT_BUILD D, ZT_STORYRELATION SR, ZT_KEYWORDS KW ' \
              'WHERE S.ID = SB.RELATEID AND SB.BUILD = D.ID AND S.ID = SR.STORY AND SR.CUSTOMER = KW.ID ' \
              'AND SB.TYPE = "story" AND S.PRODUCT IN (15,23) AND S.DELETED = "0" AND S.STATUS <> "closed" ' \
              'AND D.DELETED = "0" AND NOT D.NAME LIKE "PT%" AND D.NAME = {version}' \
              'UNION ALL ' \
              'SELECT C1. NAME 版本号, "BUG" 类型, A.ID 编号, A.TITLE 名称, KW. NAME 客户, C1.DATE 发布日期 ' \
              'FROM ZT_BUG A LEFT JOIN ZT_BUILDSTORYBUG C ON A.ID = C.RELATEID LEFT JOIN ZT_BUILD C1 ON A.PRODUCT = C1.PRODUCT ' \
              'AND C.BUILD = C1.ID JOIN ZT_BUGRELATION SR ON A.ID = SR.BUG JOIN ZT_KEYWORDS KW ON SR.CUSTOMER = KW.ID ' \
              'WHERE C1. NAME = {version}  AND A.PRODUCT IN (15,23) AND A.FOUND IN ("PRODUCTIONRUN", "BVT") ORDER BY 编号'.format(
            version='"V' + version + '"')
        # 禅道链接
        con = pymysql.connect(host='112.74.115.12', user='root', password='Scxx_150906', database='zentao_qy', charset='utf8')
        cur = con.cursor()
        cur.execute(sql)
        heads = []
        for i, j in enumerate(cur.description):
            heads.append(j[0])
        data = cur.fetchall()
        cur.close()
        con.close()

        filename = os.path.join(runDir, 'V' + version + '发布内容.xls')
        wbk = xlwt.Workbook()
        sheet1 = wbk.add_sheet('发布清单', cell_overwrite_ok=True)
        # 列头
        for i, head in enumerate(heads):
            sheet1.write(0, i, head)

        # 内容
        for row in range(1, len(data) + 1):
            for col in range(0, len(heads)):
                # 日期字段
                if col == 5:
                    datastyle = xlwt.XFStyle()
                    datastyle.num_format_str = 'yyyy-mm-dd'
                    sheet1.write(row, col, data[row - 1][col], datastyle)
                else:
                    sheet1.write(row, col, data[row - 1][col])

                # 设置合适列宽
                sheet1.col(col).width = 256 * 10
                if col == 3:
                    sheet1.col(col).width = 256 * 100
        wbk.save(filename)
        logger.info('生成发布清单excel成功!')

    except Exception as ex:
        logger.error('生成版本信息失败!' + ex)


# 检查执行脚本是否有报错
def CheckDbError():
    script_name = 'V%s.sql' % version
    with open(os.path.join(project_dir, 'dblog.txt'), 'r') as file:
        errorflag = False
        linestore = [''] * 10  # 往前取10行错误日志
        for line in file:
            for i in range(9):
                linestore[i] = linestore[i + 1]
            linestore[9] = line
            if '正在执行' in line:
                # 正在执行0-ETL_SQL.sql...
                script_name = line[4:][:-4]
            if 'ORA-' in line or 'SP2-' in line:
                errorflag = True
                logger.error('检测到脚本执行错误!【' + script_name + '】')
                logger.error("".join(linestore))
        if errorflag:
            sys.exit(1)
        else:
            logger.info('脚本无执行错误.')

def _read_config(file):
    keys = []
    with open(file,'r',encoding='utf8') as f:
        for l in f:
            if not l.startswith('#') and not l.strip()=='' and '=' in l:
                keys.append(l.split('=')[0].strip())
    return keys

# 检查配置是否缺失
def CheckConfig(dbconn):

    # 检查配置文件是否缺失参数
    test_conf = _read_config('D:\\config\\sysConfig.properties')#目前写死sysConfig路径，以后再实现根据tomcat定位
    dev_conf = _read_config(os.path.join(project_dir,'scxx-web','src','main','resources','config','sysConfig.properties'))
    for c in dev_conf:
        if c not in test_conf:
            logger.error('Error！测试环境配置文件sysConfig.properties缺少参数[%s]，请注意及时添加！' % c)
            sys.exit(1)
    logger.info('配置文件检查无误.')

    # 调用检查数据的存储过程
    logger.info('调用检查数据的存储过程...')
    conn = cx_Oracle.connect(dbconn)
    cursor = conn.cursor()
    error_c = cursor.var(cx_Oracle.STRING)
    error_m = cursor.var(cx_Oracle.STRING)
    cursor.callproc('pa_autotest.check_base_data_tran',[error_c,error_m])
    logger.info(error_m.getvalue())
    if error_c.getvalue() != '0':
        logger.error('数据库配置检查数据失败!')
        sys.exit(1)
    else:
        logger.info('数据库配置检查无误.')

if __name__ == '__main__':
    os.chdir(workDir)
    initLog()

    if len(sys.argv) == 1:#如果直接执行该脚本,参数则用下面配置的
        version = '1.8.8'#版本号
        version_l = '1.8.7'#上个版本号
        project_dir = r'J:\trunk'#源码路径
        tomcat_dir = r'D:\app\apache-tomcat-8.5.73'#tomcat路径
        dbconn_test = r'paladin/1@192.168.72.110:1521/pdbtest'#测试库链接
    elif len(sys.argv) == 7:
        type = sys.argv[1]
        version = sys.argv[2]
        version_l = sys.argv[3]
        project_dir = os.path.join(map_disk,sys.argv[4])
        tomcat_dir = sys.argv[5]
        dbconn_test = sys.argv[6]
    else:
        logger.error('参数有误！')
        sys.exit(1)
    
    if type=='deploy':
        Deploy()
        sys.exit(0)
    elif type=='rundb':
        pass
    
    project_script_dir = os.path.join(project_dir,'doc','数据库修改')#数据库脚本路径
    #整理版本文件夹
    CreateVerDir()
    #导出表结构
    PrepareDb()
    #获取变更脚本
    GetDiffScript(version,version_l,r'{project_script_dir}?全系统共用\PUB,场外脚本\配置脚本\PUB_INT,场外脚本\配置脚本\PUB_定时任务,场外脚本\配置脚本\PUB_读数接口?compare-script\数据库修改'.format(project_script_dir=project_script_dir))
    #整理脚本
    GenerateScript()
    #执行脚本
    ExecDb(dbconn_test)
    #停止tomcat,部署war，启动tomcat
    Deploy()
    #生成版本记录
    CreateExchange()
    #检查脚本执行报错
    CheckDbError()
    #检查配置是否缺失
    CheckConfig(dbconn_test)
