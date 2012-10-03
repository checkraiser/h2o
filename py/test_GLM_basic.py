import os, json, unittest, time, shutil, sys
import h2o, h2o_cmd as cmd


class Basic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        h2o.clean_sandbox()
        global nodes
        nodes = h2o.build_cloud(node_count=1)

    @classmethod
    def tearDownClass(cls):
        h2o.tear_down_cloud(nodes)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_A_Basic(self):
        for n in nodes:
            c = n.get_cloud()
            self.assertEqual(c['cloud_size'], len(nodes), 'inconsistent cloud size')

    def test_B_benign(self):
        print "\nStarting benign.csv"
        timeoutSecs = 2
        
        # columns start at 0
        Y = "3"
        X = ""
        # cols 0-13. 3 is output
        # no member id in this one
        for appendX in xrange(14):
            if (appendX == 1): 
                print "\nSkipping 1. Causes NaN. Ok now, later though?"
            elif (appendX == 2): 
                print "\nSkipping 2. Causes NaN. Ok now, later though?"
            elif (appendX == 3): 
                print "\n3 is output."
            else:
                if X == "": 
                    X = str(appendX)
                else:
                    X = X + "," + str(appendX)

                sys.stdout.write('.')
                sys.stdout.flush()
                csvFilename = "benign.csv"
                csvPathname = "../smalldata/logreg" + '/' + csvFilename
                print "\nX:", X
                print "Y:", Y

                ### FIX! add some expected result checking
                glm = cmd.runGLM(csvPathname=csvPathname, X=X, Y=Y, 
                    timeoutSecs=timeoutSecs)
                ### {u'h2o': u'/192.168.0.37:54321', u'Intercept': -1.0986109988055501, u'response_html': u'<div class=\'alert alert-success\'>Linear regression on data <a href=____9f961-8a18-4863-81ca-159ff76315f9>9f961-8a18-4863-81ca-159ff76315f9</a> computed in 20[ms]<strong>.</div><div class="container">Result Coeficients:<div>STR = -4.163336342344337E-16</div><div>Intercept = -1.0986109988055501</div></div>', u'STR': -4.163336342344337e-16, u'time': 20}

                # print glm
                print "STR:", glm['STR']
                print "Intercept:", glm['Intercept']

    def test_C_prostate(self):
        timeoutSecs = 2
        
        print "\nStarting prostate.csv"
        # columns start at 0
        Y = "1"
        X = ""
        for appendX in xrange(9):
            if (appendX == 0):
                print "\n0 is member ID. not used"
            elif (appendX == 1):
                print "\n1 is output."
            elif (appendX == 7): 
                print "\nSkipping 7. Causes NaN. Ok now, later though?"
            else:
                if X == "": 
                    X = str(appendX)
                else:
                    X = X + "," + str(appendX)

                sys.stdout.write('.')
                sys.stdout.flush() 
                csvFilename = "prostate.csv"
                csvPathname = "../smalldata/logreg" + '/' + csvFilename
                print "\nX:", X
                print "Y:", Y

                ### FIX! add some expected result checking
                ### ..{u'h2o': u'/192.168.1.17:54321', u'Intercept': -0.25720656777427364, u'ID': -0.000723962423344251, u'response_html': u'<div class=\'alert alert-success\'>Linear regression on data <a href=____6aebc-a37f-465e-bd4e-3bd0a3a5828c>6aebc-a37f-465e-bd4e-3bd0a3a5828c</a> computed in 21[ms]<strong>.</div><div class="container">Result Coeficients:<div>ID = -7.23962423344251E-4</div><div>Intercept = -0.25720656777427364</div></div>', u'time': 21}
                glm = cmd.runGLM(csvPathname=csvPathname, X=X, Y=Y, timeoutSecs=timeoutSecs)
                # print "glm:", glm
                print "AGE:", glm['AGE']
                print "Intercept:", glm['Intercept']


import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # can add more here
    parser.add_argument('--verbose','-v', help="increased output", action="store_true")
    
    parser.add_argument('unittest_args', nargs='*')
    args = parser.parse_args()

    # hmm. is there a better way to resolve the namespace issue?
    h2o.verbose = args.verbose

    # set sys.argv to the unittest args (leav sys.argv[0] as is)
    sys.argv[1:] = args.unittest_args

    # print "\nh2o.verbose:", h2o.verbose
    unittest.main()

