import os, json, unittest, time, shutil, sys
import h2o, cmd

class Basic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h2o.build_cloud(node_count=3)

    @classmethod
    def tearDownClass(cls):
        h2o.tear_down_cloud()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_RFhhp(self):
        # FIX! we're supposed to be support gzip files but seems to fail
        # normally we .gz for the git, to save space
        # we do take .zip directly. bug fix needed for .gz

        # 0-32 output class values
        ### csvPathname = '../smalldata/hhp_50.short3.data'

        # 0-15 output class values
        ## csvPathname = '../smalldata/hhp_107_01_short.data'

        # don't want to worry about timeout on RF, so just take the first 100 rows
        # csvPathname = '../smalldata/hhp_9_17_12.predict.data'
        csvPathname = '../smalldata/hhp.cut3.214.data'

        if not os.path.exists(csvPathname) :
            # check if the gz exists (git will have the .gz)
            if os.path.exists(csvPathname + '.gz') :
                # keep the .gz in place
                h2o.spawn_cmd_and_wait(
                    'gunzip', 
                    ['gunzip', csvPathname + '.gz'], 
                    timeout=4)
            else:
                raise Exception("Can't find %s or %s.gz" % (csvPathname, csvPathname))

        # FIX! TBD do we always have to kick off the run from node 0?
        # what if we do another node?
        print "RF start on ", csvPathname, "this will probably take a minute.."
        start = time.time()
        cmd.runRF(csvPathname=csvPathname, trees=23,
                timeoutSecs=120, retryDelaySecs=10)
        print "RF end on ", csvPathname, 'took', time.time() - start, 'seconds'

if __name__ == '__main__':
    h2o.clean_sandbox()
    unittest.main()
