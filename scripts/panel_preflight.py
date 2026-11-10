"""Non-destructive checks before a local panel demonstration."""
import sys,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx
from backend.config import Settings
from backend.utils.local_endpoints import validate_model_endpoints


def main():
    settings=Settings();checks={}
    def check(name,function):
        try:checks[name]={'ok':True,'detail':function()}
        except Exception as error:checks[name]={'ok':False,'detail':type(error).__name__+': '+str(error)}
    def policy():
        if not settings.local_only:raise RuntimeError('Enable local-only mode before the demonstration')
        validate_model_endpoints(settings)
        return {'local_only':True}
    check('local_model_policy',policy)
    with httpx.Client(timeout=15,trust_env=False,follow_redirects=False) as client:
        def endpoint(url):
            response=client.get(url);response.raise_for_status();return response
        check('backend',lambda:endpoint('http://127.0.0.1:8000/health').json())
        check('frontend',lambda:{'http_status':endpoint('http://127.0.0.1:5173/').status_code})
        def models():
            ids=[m['id'] for m in endpoint(settings.lmstudio_base_url+'/models').json()['data']]
            required=[settings.lmstudio_model,settings.embedding_model]
            if not all(m in ids for m in required):raise RuntimeError('Required generator or embedding model is unavailable')
            return {'available_models':required,'note':'Inventory check; inference is verified by the integration runs.'}
        check('models',models)
        def routes():
            paths=endpoint('http://127.0.0.1:8000/openapi.json').json()['paths']
            expected=[('/chat/{chat_id}/messages/{message_id}','patch'),('/chat/{chat_id}/messages/{message_id}','delete'),('/chat/{chat_id}/forget','post'),('/chat/{chat_id}/images','post')]
            if not all(method in paths.get(path,{}) for path,method in expected):raise RuntimeError('Backend needs restart; required routes missing')
            parameters=paths['/memory/debug']['get'].get('parameters',[])
            if not any(p['name']=='X-User-Id' and p.get('required') for p in parameters):raise RuntimeError('Restart backend to enable learner-scoped diagnostics')
            return {'update_delete_forget_image_routes':'present'}
        check('routes',routes)
    def mysql():
        if not settings.mysql_enabled:raise RuntimeError('MySQL is not enabled for this tutor')
        import mysql.connector
        credentials=json.loads(settings.mysql_credentials_file.read_text())
        connection=mysql.connector.connect(**credentials,connection_timeout=5)
        try:
            cursor=connection.cursor();cursor.execute('SELECT 1');assert cursor.fetchone()==(1,)
        finally:connection.close()
        return {'enabled':settings.mysql_enabled,'host':'127.0.0.1','port':credentials['port']}
    def graph():
        if not settings.graph_enabled:raise RuntimeError('Neo4j is not enabled for this tutor')
        from neo4j import GraphDatabase
        credentials=json.loads(settings.graph_credentials_file.read_text())
        with GraphDatabase.driver(settings.graph_uri,auth=(credentials['username'],credentials['password']),telemetry_disabled=True) as driver:driver.verify_connectivity()
        return {'enabled':settings.graph_enabled,'uri':settings.graph_uri}
    check('mysql',mysql);check('neo4j',graph)
    def ocr():
        binary=shutil.which('tesseract');weights=ROOT/'ocr_models/tessdata_best/eng.traineddata'
        if not binary or not weights.is_file():raise RuntimeError('Local OCR engine or English weights missing')
        return {'engine':'tesseract','local_weights':True}
    check('ocr',ocr)
    report={'ready':all(c['ok'] for c in checks.values()),'memory_configuration':settings.memory_configuration,
        'checks':checks,'scope':'Local demonstration readiness, not a security audit or an accuracy guarantee.'}
    print(json.dumps(report,indent=2));return 0 if report['ready'] else 1

if __name__=='__main__':raise SystemExit(main())
