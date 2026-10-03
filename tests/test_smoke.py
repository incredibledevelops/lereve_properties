def test_healthz(client):
    r = client.get('/healthz')
    assert r.status_code == 200


def test_landing(client):
    r = client.get('/')
    assert r.status_code == 200
    assert b'Le R' in r.data


def test_login_page(client):
    r = client.get('/login')
    assert r.status_code == 200


def test_robots(client):
    r = client.get('/robots.txt')
    assert r.status_code == 200
    assert b'Sitemap' in r.data


def test_sitemap(client):
    r = client.get('/sitemap.xml')
    assert r.status_code == 200


def test_client_redirects_to_login(client):
    r = client.get('/client/dashboard', follow_redirects=False)
    assert r.status_code in (301, 302)


def test_admin_redirects_to_login(client):
    r = client.get('/admin/dashboard', follow_redirects=False)
    assert r.status_code in (301, 302)