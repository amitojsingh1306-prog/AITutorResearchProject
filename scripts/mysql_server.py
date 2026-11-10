"""Control only this project's isolated MySQL instance (port 3307)."""
import argparse,json,os,signal,socket,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def ready():
    import mysql.connector
    try:
        credentials=json.loads((ROOT/'.local/mysql_credentials.json').read_text())
        connection=mysql.connector.connect(**credentials,connection_timeout=2)
        connection.close();return True
    except (OSError,mysql.connector.Error):return False

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','status','stop'],default='status',nargs='?')
    args=parser.parse_args();directory=ROOT/'.local/mysql'
    if args.action=='stop':
        import mysql.connector
        credentials=json.loads((ROOT/'.local/mysql_admin.json').read_text())
        connection=mysql.connector.connect(**credentials)
        connection.cmd_shutdown();connection.close();print('Project MySQL stopped.')
    elif ready():print('Project MySQL is ready on 127.0.0.1:3307.')
    elif args.action=='status':raise SystemExit('Project MySQL is not running.')
    else:
        subprocess.run(['/usr/local/mysql/bin/mysqld','--defaults-file='+str(directory/'my.cnf'),'--daemonize'],check=True)
        for _ in range(45):
            if ready():print('Project MySQL is ready on 127.0.0.1:3307.');break
            time.sleep(1)
        else:raise SystemExit('MySQL did not become ready; inspect .local/mysql/mysql.log.')
