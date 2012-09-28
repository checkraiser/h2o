import time, os, json, signal, tempfile, shutil, datetime, inspect
import requests
import psutil

def verboseprint(*args):
    ### global verbose
    if 1==0: # change to 1==1 if you want verbose
        for arg in args: # so you don't have to create a single string
           print arg,
        print

def find_file(base):
    f = base
    if not os.path.exists(f): f = '../'+base
    return f

LOG_DIR = 'sandbox'
def clean_sandbox():
    if os.path.exists(LOG_DIR):
        # shutil.rmtree fails to delete very long filenames on Windoze
        #shutil.rmtree(LOG_DIR)
        # This seems reliable on windows+cygwin
        os.system("rm -rf "+LOG_DIR);
    os.mkdir(LOG_DIR)

def tmp_file(prefix='', suffix=''):
    return tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=LOG_DIR)
def tmp_dir(prefix='', suffix=''):
    return tempfile.mkdtemp(prefix=prefix, suffix=suffix, dir=LOG_DIR)

def log(cmd, comment=None):
    with open(LOG_DIR + '/commands.log', 'a') as f:
        f.write(str(datetime.datetime.now()) + ' -- ')
        f.write(cmd)
        if comment:
            f.write('    #')
            f.write(comment)
        f.write("\n")

# Hackery: find the ip address that gets you to Google's DNS
# Trickiness because you might have multiple IP addresses (Virtualbox), or Windows.
# Will fail if local proxy? we don't have one.
# Watch out to see if there are NAT issues here (home router?)
# Could parse ifconfig, but would need something else on windows
def get_ip_address():
    import socket
    ip = '127.0.0.1'
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8',0))
        ip = s.getsockname()[0]
        verboseprint("ip1:", ip)

    except:
        pass

    if ip.startswith('127'):
        ip = socket.getaddrinfo(socket.gethostname(), None)[0][4][0]

    verboseprint("get_ip_address:", ip) 
    return ip

def spawn_cmd(name, args):
    outfd,outpath = tmp_file(name + '.stdout.', '.log')
    errfd,errpath = tmp_file(name + '.stderr.', '.log')
    ps = psutil.Popen(args, stdin=None, stdout=outfd, stderr=errfd)
    comment = 'PID %d, stdout %s, stderr %s' % (
        ps.pid, os.path.basename(outpath), os.path.basename(errpath))
    log(' '.join(args), comment=comment)
    return (ps, outpath, errpath)

def spawn_cmd_and_wait(name, args, timeout=None):
    (ps, stdout, stderr) = spawn_cmd(name, args)

    rc = ps.wait(timeout)
    out = file(stdout).read()
    err = file(stderr).read()

    if rc is None:
        ps.terminate()
        raise Exception("%s %s timed out after %d\nstdout:\n%s\n\nstderr:\n%s" %
                (name, args, timeout or 0, out, err))
    elif rc != 0:
        raise Exception("%s %s failed.\nstdout:\n%s\n\nstderr:\n%s" % (name, args, out, err))

def spawn_h2o(addr=None, port=54321, nosigar=True):
    # temporary hack changing this line, so can run with jre, not jdk
    # because we currently need tools.jar
    # "java", "-ea", "-jar", find_file('build/h2o.jar'),
    h2o_cmd = [
            "java", 
            "-javaagent:" + find_file('build/h2o.jar'),
            "-ea", "-jar", find_file('build/h2o.jar'),
            "--port=%d"%port,
            '--ip=%s'%(addr or get_ip_address()),
            '--ice_root=%s' % tmp_dir('ice.')
            ]
    if nosigar is True: 
        h2o_cmd.append('--nosigar')
    return spawn_cmd('h2o', h2o_cmd)

nodes = []
def build_cloud(node_count, base_port=54321, ports_per_node=3, addr=None, nosigar=True):
    node_list = []
    try:
        for i in xrange(node_count):
            n = H2O(addr,port=base_port + i*ports_per_node,nosigar=nosigar)
            node_list.append(n)
        stabilize_cloud(node_list[0], len(node_list))
    except:
        for n in node_list: n.terminate()
        raise
    nodes[:] = node_list
    return node_list

def tear_down_cloud(node_list=None):
    if not node_list: node_list = nodes

    ex = None
    try:
        for n in node_list:
            if n.wait() is None:
                n.terminate()
            elif n.wait():
                ex = Exception('Node terminated with non-zero exit code: %d' % n.wait())
        if ex: raise ex
    finally:
        node_list[:] = []

def stabilize_cloud(node, node_count, timeoutSecs=10.0, retryDelaySecs=0.25):
    node.stabilize('cloud auto detect', timeoutSecs,
        lambda n: n.get_cloud()['cloud_size'] == node_count,
        retryDelaySecs)

class H2O:
    def __url(self, loc):
        return 'http://%s:%d/%s' % (self.addr, self.port, loc)

    def __check_request(self, r):
        log('Sent ' + r.url)
        if not r:
            raise Exception('Error in %s: %s' % (inspect.stack()[1][3], str(r)))
        # json name used in import
        rjson = r.json
        if 'error' in rjson:
            raise Exception('Error in %s: %s' % (inspect.stack()[1][3], rjson['error']))
        return rjson

    def __check_spawn(self):
        if not self.ps:
            import inspect
            raise Exception('Error in %s: %s' % (inspect.stack()[1][3], 'process was not spawned'))

    def get_cloud(self):
        a = self.__check_request(requests.get(self.__url('Cloud.json')))
        verboseprint ("get_cloud:", a)
        return a

    def put_value(self, value, key=None, repl=None):
        return self.__check_request(
            requests.get(self.__url('PutValue.json'), 
                params={"Value": value, "Key": key, "RF": repl}
                ))

    def put_file(self, f, key=None, repl=None):
        return self.__check_request(
            requests.post(self.__url('PutFile.json'), 
                files={"File": open(f, 'rb')},
                params={"Key": key, "RF": repl} # key is optional. so is repl factor (called RF)
                ))

    # FIX! placeholder..what does the JSON really want?
    def get_file(self, f):
        return self.__check_request(requests.post(self.__url('GetFile.json'), 
            files={"File": open(f, 'rb')}))

    def parse(self, key):
        return self.__check_request(requests.get(self.__url('Parse.json'),
            params={"Key": key}))

    def netstat(self):
        return self.__check_request(requests.get(self.__url('Network.json')))

    def inspect(self, key):
        return self.__check_request(requests.get(self.__url('Inspect.json'),
            params={"Key": key}))

    # FIX! add depth/ntrees to all calls?
    def random_forest(self, key, ntrees=6, depth=30):
        return self.__check_request(requests.get(self.__url('RF.json'),
            params={
                "depth": depth,
                "ntrees": ntrees,
                "Key": key
                }))

    def random_forest_view(self, key):
        a = self.__check_request(requests.get(self.__url('RFView.json'),
            params={"Key": key}))
        verboseprint("random_forest_view:", a)
        return a

    def stabilize(self, msg, timeoutSecs, func, retryDelaySecs=0.5):
        '''Repeatedly test a function waiting for it to return True.

        Arguments:
        msg         -- A message for displaying errors to users
        retryDelaySecs -- How long in seconds to wait before retrying
        func        -- A function that will be called with the node as an argument.
                    -- return True for success or False for continue waiting
        timeoutSecs -- How long in seconds to keep trying before declaring a failure
        '''

        start = time.time()
        retryCount = 0
        while time.time() - start < timeoutSecs:
            if func(self):
                break
            retryCount += 1
            verboseprint("stabilize retry:", retryCount)
            # tests should call with retry delay at maybe 1/2 expected times 
            # so retrying more than 12 times is an error. easier to debug?
            if retryCount > 12:
                raise Exception("stabilize retried too much. Bug or extend retry delay?: %d\n" % (retryCount))

            verboseprint("sleep:", retryDelaySecs)
            time.sleep(retryDelaySecs)
        else:
            raise Exception('Timeout waiting for condition: ' + msg)

    def __is_alive(self, s2):
        assert self == s2
        try:
            n = self.get_cloud()
            verboseprint("__isalive:", n)
            return True
        except requests.ConnectionError, e:
            verboseprint("__isalive ConnectionError")
            if e.args[0].errno == 61 or e.args[0].errno == 10061 or e.args[0].errno == 111:
                return False
            raise

    def __init__(self, addr=None, port=54321, spawn=True, nosigar=True):
        self.port = port
        self.addr = addr or get_ip_address()
        verboseprint("addr:", addr)
        verboseprint("get_ip_address", get_ip_address())
        verboseprint("Using ip:", self.addr)

        if not spawn:
            self.stabilize('h2o started', 4, self.__is_alive)
        else:
            self.rc = None
            spawn = spawn_h2o(addr=self.addr, port=port, nosigar=nosigar)
            self.ps = spawn[0]
            try:
                self.stabilize('h2o started', 4, self.__is_alive)
            except:
                self.ps.kill()
                raise

            if self.wait():
                out = file(spawn[1]).read()
                err = file(spawn[2]).read()
                raise Exception('Failed to launch with exit code: %d\nstdout:\n%s\n\nstderr:\n%s' % 
                    (self.wait(), out, err))

    def stack_dump(self):
        self.__check_spawn()
        self.ps.send_signal(signal.SIGQUIT)
    

    def wait(self, timeout=0):
        self.__check_spawn()
        if self.rc: return self.rc
        try:
            self.rc = self.ps.wait(timeout)
            return self.rc
        except psutil.TimeoutExpired:
            return None

    def terminate(self):
        self.__check_spawn()
        if not self.wait():
            self.ps.kill()
        if not self.wait():
            self.ps.terminate()
        return self.wait()
