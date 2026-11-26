"""Play two public game URLs using the Mobile Safari W3C WebDriver session."""
import json
import os
import subprocess
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path


evidence = Path('safari-evidence')
evidence.mkdir(exist_ok=True)
driver = 'http://127.0.0.1:4444'
session = ''


def call(method, route, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(driver + session + route, data=body, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return json.load(response)['value']
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode()[:1800]) from exc


def wait(check, seconds=45):
    end = time.monotonic() + seconds
    while True:
        value = check()
        if value:
            return value
        if time.monotonic() >= end:
            raise TimeoutError(check)
        time.sleep(0.5)


def js(script, *args):
    return call('POST', '/execute/sync', {'script': script, 'args': args})


def visible(selector):
    return js('const e=document.querySelector(arguments[0]); return !!(e && e.getClientRects().length && getComputedStyle(e).visibility!=="hidden");', selector)


def element(selector):
    wait(lambda: visible(selector))
    return next(iter(call('POST','/element',{'using':'css selector','value':selector}).values()))


def click(selector):
    call('POST', '/element/' + element(selector) + '/click', {})


def confirm_recipient():
    click('.prayer-form button[type=submit]')
    wait(lambda:'River' in text_of('.prayer-current'))


def type_into(selector, text):
    ref=element(selector)
    call('POST','/element/'+ref+'/click',{})
    call('POST','/element/'+ref+'/value',{'text':text})
    assert js('return document.querySelector(arguments[0]).value',selector)==text


def screenshot(name):
    subprocess.run(['xcrun','simctl','io',os.environ['SIM_UDID'],'screenshot',str(evidence/(name+'.png'))],check=True)


def text_of(selector):
    return js('return document.querySelector(arguments[0])?.innerText||""', selector)


def garden():
    call('POST','/url',{'url':'https://cyber-cemetery-proto.pages.dev/'})
    assert 'v0.64' in call('GET','/title')
    click('#btnTitleMain')
    click('[data-av=a4]')
    click('#btnMapTop')
    click('#btnNearestPlot')
    wait(lambda:visible('#btnRegHere'),60)
    click('#btnRegHere')
    type_into('#regName','Momo')
    screenshot('garden-name-keyboard')
    click('#btnRegister')
    click('#btnSkipCer')
    click('#btnFirstCandle')
    wait(lambda:'Momo' in text_of('#infoName'))
    click('#btnMapTop')
    click('.mapBadge.home')
    click('[data-act=feed]')
    click('[data-act=play]')
    wait(lambda:'被投喂 1' in text_of('#houseStats') and '被陪玩 1' in text_of('#houseStats'))
    screenshot('garden-house')
    click('#btnLeave')
    click('#btnDrawer')
    click('#btnLoginGift')
    click('#btnCheckin')
    call('POST','/refresh',{})
    click('#btnTitleLoad')
    click('#btnDrawer')
    wait(lambda:'今日已签到' in text_of('#checkinLabel') and '今日物资已领' in text_of('#giftLabel'))


def mountain():
    call('POST','/url',{'url':'https://yunqi-shanzhong-v2-play.pages.dev/'})
    type_into('#nick','River')
    screenshot('mountain-name-keyboard')
    click('#enter')
    wait(lambda: visible('#lookPicker') or visible('#tripSkip') or visible('#btnMap'))
    if visible('#lookPicker'):
        click('#lookChoices button')
        click('#lookConfirm')
    wait(lambda:visible('#tripSkip') or visible('#btnMap'))
    if visible('#tripSkip'):
        click('#tripSkip')
    click('#btnMap')
    click('.mpAct[data-hot="hall"]')
    wait(lambda:visible('.prayer-panel'),100)
    type_into('.prayer-form input','River')
    confirm_recipient()
    screenshot('mountain-hall')
    click('#mgExit')
    click('#btnMap')
    click('.mpAct[data-hot="qin"]')
    wait(lambda:visible('.prayer-panel'),100)
    type_into('.prayer-form input','River')
    confirm_recipient()
    ref=call('POST','/element',{'using':'xpath','value':'//button[normalize-space(.)="点一盏烛"]'})
    call('POST','/element/'+next(iter(ref.values()))+'/click',{})
    click('.prayer-paper[data-kind="cloud"]')
    click('.prayer-sheet-control')
    wait(lambda:'送纸 1 张' in text_of('.prayer-current'))
    screenshot('mountain-offering')


def main():
    global session
    caps={'browserName':'Safari','platformName':'iOS','safari:useSimulator':True,
          'safari:deviceUDID':os.environ['SIM_UDID']}
    for i in range(8):
        try:
            created=call('POST','/session',{'capabilities':{'alwaysMatch':caps}})
            break
        except (OSError,RuntimeError) as error:
            if i==7:
                raise
            print('Driver startup:',error,flush=True)
            time.sleep(3)
    session='/session/'+created['sessionId']
    capabilities=created['capabilities']
    assert capabilities['platformName'].lower()=='ios' and capabilities['safari:useSimulator']
    print('SIMULATOR',capabilities['safari:deviceName'],capabilities['safari:platformVersion'],capabilities['browserVersion'],flush=True)
    report={'capabilities':capabilities, 'games':{}}
    for fn in (garden,mountain):
        try:
            fn()
            report['games'][fn.__name__]='PASS'
        except Exception:
            traceback.print_exc()
            report['games'][fn.__name__]='FAIL'
            screenshot(fn.__name__+'-failure')
        print(fn.__name__,report['games'][fn.__name__],flush=True)
    (evidence/'results.json').write_text(json.dumps(report,indent=2))
    call('DELETE','')
    if 'FAIL' in report['games'].values():
        raise SystemExit(1)


if __name__=='__main__':
    main()
