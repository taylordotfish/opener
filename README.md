Opener
======

Opener is a JavaScript deobfuscator. Certain JavaScript minifiers, like Closure
Compiler, modify the AST in ways that make it difficult for pretty-printers to
achieve good results. Opener applies its own set of AST transformations
designed to make pretty-printing successful.

Example
-------

Given this code (from the minified version of jQuery 3.6.0; see
[misc/jquery-license.txt](misc/jquery-license.txt)):

```javascript
S.offset={setOffset:function(e,t,n){var r,i,o,a,s,u,l=S.css(e,"position"),c=S(e),f={};"static"===l&&(e.style.position="relative"),s=c.offset(),o=S.css(e,"top"),u=S.css(e,"left"),("absolute"===l||"fixed"===l)&&-1<(o+u).indexOf("auto")?(a=(r=c.position()).top,i=r.left):(a=parseFloat(o)||0,i=parseFloat(u)||0),m(t)&&(t=t.call(e,n,S.extend({},s))),null!=t.top&&(f.top=t.top-s.top+a),null!=t.left&&(f.left=t.left-s.left+i),"using"in t?t.using.call(e,f):c.css(f)}}
```

When simply passed through a pretty-printer, we get:

```javascript
S.offset = {
    setOffset: function (e, t, n) {
        var r, i, o, a, s, u, l = S.css(e, 'position'), c = S(e), f = {};
        'static' === l && (e.style.position = 'relative'), s = c.offset(), o = S.css(e, 'top'), u = S.css(e, 'left'), ('absolute' === l || 'fixed' === l) && -1 < (o + u).indexOf('auto') ? (a = (r = c.position()).top, i = r.left) : (a = parseFloat(o) || 0, i = parseFloat(u) || 0), m(t) && (t = t.call(e, n, S.extend({}, s))), null != t.top && (f.top = t.top - s.top + a), null != t.left && (f.left = t.left - s.left + i), 'using' in t ? t.using.call(e, f) : c.css(f);
    }
};
```

…which isn’t much easier to read. But when passed through Opener, we get:

```javascript
S.offset = {
    setOffset: function (e, t, n) {
        var r;
        var i;
        var o;
        var a;
        var s;
        var u;
        var l = S.css(e, 'position');
        var c = S(e);
        var f = {};
        if ('static' === l) {
            e.style.position = 'relative';
        }
        s = c.offset();
        o = S.css(e, 'top');
        u = S.css(e, 'left');
        if (('absolute' === l || 'fixed' === l) && -1 < (o + u).indexOf('auto')) {
            a = (r = c.position()).top;
            i = r.left;
        } else {
            a = parseFloat(o) || 0;
            i = parseFloat(u) || 0;
        }
        if (m(t)) {
            t = t.call(e, n, S.extend({}, s));
        }
        if (null != t.top) {
            f.top = t.top - s.top + a;
        }
        if (null != t.left) {
            f.left = t.left - s.left + i;
        }
        if ('using' in t) {
            t.using.call(e, f);
        } else {
            c.css(f);
        }
    }
};
```

Installation
------------

Opener requires:

* Python ≥ 3.9
* Node.js ≥ 12

Clone the repository and enter the directory:

```bash
git clone https://github.com/taylordotfish/opener
cd opener
```

Install the required Python packages (you can use `requirements.freeze.txt`
instead to install specific versions of the dependencies that have been
verified to work):

```bash
pip3 install -r requirements.txt
```

And install the required NPM packages:

```bash
npm install
```

Then, you can run `./opener.py`.

Usage
-----

See `./opener.py --help`. The deobfuscated code is written to standard output.

License
-------

Opener is licensed under version 3 of the GNU Affero General Public License, or
(at your option) any later version. See [LICENSE](LICENSE).

Contributing
------------

By contributing to Opener, you agree that your contribution may be used
according to the terms of Opener’s license.
