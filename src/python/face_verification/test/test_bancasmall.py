#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Laurent El Shafey <Laurent.El-Shafey@idiap.ch>

"""Test trainer package
"""
import os, sys, tempfile, shutil
import unittest
import torch


def NormalizeStdArrayset(arrayset):
  arrayset.load()

  length = arrayset.shape[0]
  n_samples = len(arrayset)
  mean = torch.core.array.float64_1(length)
  std = torch.core.array.float64_1(length)

  mean.fill(0)
  std.fill(0)

  for array in arrayset:
    x = array.get().cast('float64')
    mean += x
    std += (x ** 2)

  mean /= n_samples
  std /= n_samples
  std -= (mean ** 2)
  std = std ** 0.5 # sqrt(std)

  arStd = torch.io.Arrayset()
  for array in arrayset:
    arStd.append(array.get().cast('float64') / std)

  return (arStd,std)


def multiplyVectorsByFactors(matrix, vector):
  for i in range(0, matrix.rows()):
    for j in range(0, matrix.columns()):
      matrix[i, j] *= vector[j]


def loadData(files):
  data = torch.io.Arrayset()
  for f in files:
    data.extend(torch.io.Array(str(f)))

  return data


def trainGMM(data, n_gaussians=5, iterk=25, iterg=25, convergence_threshold=1e-5, variance_threshold=0.001, 
             update_weights=True, update_means=True, update_variances=True, norm_KMeans=False):
  ar = data

  # Compute input size
  input_size = ar.shape[0]

  # Create a normalized sampler
  if not norm_KMeans:
    normalizedAr = ar
  else:
    (normalizedAr,stdAr) = NormalizeStdArrayset(ar)
    
  # Create the machines
  kmeans = torch.machine.KMeansMachine(n_gaussians, input_size)
  gmm = torch.machine.GMMMachine(n_gaussians, input_size)

  # Create the KMeansTrainer
  kmeansTrainer = torch.trainer.KMeansTrainer()
  kmeansTrainer.convergenceThreshold = convergence_threshold
  kmeansTrainer.maxIterations = iterk

  # Train the KMeansTrainer
  kmeansTrainer.train(kmeans, normalizedAr)

  [variances, weights] = kmeans.getVariancesAndWeightsForEachCluster(normalizedAr)
  means = kmeans.means

  # Undo normalization
  if norm_KMeans:
    multiplyVectorsByFactors(means, stdAr)
    multiplyVectorsByFactors(variances, stdAr ** 2)

  # Initialize gmm
  gmm.means = means
  gmm.variances = variances
  gmm.weights = weights
  gmm.setVarianceThresholds(variance_threshold)

  # Train gmm
  trainer = torch.trainer.ML_GMMTrainer(update_means, update_variances, update_weights)
  trainer.convergenceThreshold = convergence_threshold
  trainer.maxIterations = iterg
  trainer.train(gmm, ar)

  return gmm



def adaptGMM(data, prior_gmm, iterg=25, convergence_threshold=1e-5, variance_threshold=0.001, adapt_weight=False, adapt_variance=False, relevance_factor=0.001, responsibilities_threshold=0, torch3_map=False, alpha_torch3=0.5):

  ar=data

  # Load prior gmm
  prior_gmm.setVarianceThresholds(variance_threshold)

  # Create trainer
  if responsibilities_threshold == 0.:
    trainer = torch.trainer.MAP_GMMTrainer(relevance_factor, True, adapt_variance, adapt_weight)
  else:
    trainer = torch.trainer.MAP_GMMTrainer(relevance_factor, True, adapt_variance, adapt_weight, responsibilities_threshold)
  trainer.convergenceThreshold = convergence_threshold
  trainer.maxIterations = iterg
  trainer.setPriorGMM(prior_gmm)

  if torch3_map:
    trainer.setT3MAP(alpha_torch3)

  # Load gmm
  gmm = torch.machine.GMMMachine(prior_gmm)
  gmm.setVarianceThresholds(variance_threshold)

  # Train gmm
  trainer.train(gmm, ar)

  return gmm


class GMMExperiment:
  
  def __init__(self, db, features_dir, extension, protocol, wm, models_dir, linear_scoring=False, ztnorm=False):
    self.features_dir = features_dir
    self.extension = extension
    self.protocol = protocol
    self.wm = wm
    self.db = db
    self.client_models = {}
    self.models_dir = models_dir
    self.linear_scoring = linear_scoring
    self.ztnorm = ztnorm
    self.iterg = 50
    self.convergence_threshold = 1e-5
    self.variance_threshold = 0.001
    self.relevance_factor = 0.001

  def precomputeZTnorm(self, tnorm_clients, znorm_clients):
    # Loading data for ZTnorm
    # Getting models for tnorm_clients

    i = 0
    self.tnorm_models = []
    for c in tnorm_clients:
      self.tnorm_models.append(self.getModel(c))
      i += 1

    # Getting statistics for znorm_clients

    tnorm_clients_ext=[]
    i = 0
    self.znorm_tests = []
    for c in znorm_clients:
      train_files = self.db.files(directory=self.features_dir, extension=self.extension, protocol=self.protocol, purposes='probe', model_ids=(c,), groups=None, classes='client')
      for f in train_files.itervalues():
        [file_basename, x] = os.path.splitext(os.path.basename(f))
        stat_path =  os.path.join(self.models_dir, "statswm_" + file_basename + "_" + str(c) + ".hdf5")
        if os.path.exists(stat_path):
          stats = torch.machine.GMMStats(torch.io.HDF5File(str(stat_path)))
        else:
          data = loadData([f])
          stats = torch.machine.GMMStats(self.wm.nGaussians, self.wm.nInputs)
          self.wm.accStatistics(data, stats)
          stats.save(torch.io.HDF5File(str(stat_path)))

        self.znorm_tests.append(stats)
        #tnorm_clients_ext.append(c)
        r_id = self.db.getRealIdFromTNormId(c)
        tnorm_clients_ext.append(r_id)

      i += 1


    self.D = torch.machine.linearScoring(self.tnorm_models, self.wm, self.znorm_tests)
    tnorm_real_ids = []
    for c in tnorm_clients:
      r_id = self.db.getRealIdFromTNormId(c)
      tnorm_real_ids.append(r_id)
    self.D_sameValue = self.sameValue(tnorm_real_ids, tnorm_clients_ext)

    # Loading data for ZTnorm ... done"
    
  def sameValue(self, vect_A, vect_B):
    sameMatrix = torch.core.array.bool_2(len(vect_A), len(vect_B))

    for j in range(len(vect_A)):
      for i in range(len(vect_B)):
        sameMatrix[j, i] = (vect_A[j] == vect_B[i])

    return sameMatrix

  def setZTnormGroup(self, group):
      
    tnorm_clients = self.db.tnorm_ids(protocol=self.protocol)
    znorm_clients = self.db.tnorm_ids(protocol=self.protocol)

    self.precomputeZTnorm(tnorm_clients, znorm_clients)
    

  def train(self, model_id):
    # Training model
    train_files = self.db.files(directory=self.features_dir, extension=self.extension, protocol=self.protocol, purposes='enrol', model_ids=(model_id,), groups=None, classes=None)
    data = loadData(train_files.itervalues())
    gmm = adaptGMM(data, 
                   self.wm, 
                   iterg=self.iterg,
                   convergence_threshold=self.convergence_threshold,
                   variance_threshold=self.variance_threshold,
                   relevance_factor=self.relevance_factor,
                   responsibilities_threshold=self.responsibilities_threshold)
    return gmm
  
  def getModel(self, model_id):
    if not model_id in self.client_models:
      model_path = os.path.join(self.models_dir, str(model_id) + ".hdf5")
      if os.path.exists(model_path):
        self.client_models[model_id] = torch.machine.GMMMachine(torch.io.HDF5File(model_path))
      else:
        self.client_models[model_id] = self.train(model_id)
        self.client_models[model_id].save(torch.io.HDF5File(model_path))
    
    return self.client_models[model_id]
    

  def scores(self, models, files):
    if self.linear_scoring:
      list_stats=[]
      for f in files :
        data = loadData([f])
        stats = torch.machine.GMMStats(self.wm.nGaussians, self.wm.nInputs)
        self.wm.accStatistics(data, stats)
        list_stats.append(stats)
      
      scores = torch.machine.linearScoring(models, self.wm, list_stats)
    else:
      scores = torch.core.array.float64_2(len(models), len(files))
      
      nb_scores = len(models)*len(files)
      i=0
      sys.stdout.flush()
      for m in range(len(models)):
        for f in range(len(files)):
          data = loadData([files[f]])
          sumWm = 0
          sumc = 0
          for d in data:
            sumWm += self.wm.forward(d.get())
            sumc += models[m].forward(d.get())

          scores[m, f] = sumc - sumWm
          i+=1
          sys.stdout.flush()
    
    if self.ztnorm:
      # TODO: fix n_blocks
      n_blocks = 4161
      A = scores / n_blocks
      B = torch.machine.linearScoring(models, self.wm, self.znorm_tests) / n_blocks
      C = torch.machine.linearScoring(self.tnorm_models, self.wm, list_stats) / n_blocks 
      scores = torch.machine.ztnorm(A, B, C, self.D/n_blocks, self.D_sameValue)
    return scores

  def convert_score_to_list(self, scores, probes):
    ret = []
    i = 0
    for c in probes.itervalues():
      ret.append((c[1], c[2], c[3], c[4], scores[0, i]))
      i+=1

    return ret

  def scores_client(self, model_id):
    client_probes = self.db.objects(directory=self.features_dir, extension=self.extension, protocol=self.protocol, purposes="probe", model_ids=(model_id,), classes="client") 

    files = [x[0] for x in client_probes.itervalues()]
    scores = self.scores([self.getModel(model_id)], files)
    
    return self.convert_score_to_list(scores, client_probes)

  def scores_impostor(self, model_id):
    client_probes = self.db.objects(directory=self.features_dir, extension=self.extension, protocol=self.protocol, purposes="probe", model_ids=(model_id,), classes="impostor")

    files = [x[0] for x in client_probes.itervalues()]
    scores = self.scores([self.getModel(model_id)], files)
    
    return self.convert_score_to_list(scores, client_probes)

  
  def run(self, groups, output_file):
    models = self.db.models(groups=groups)
    if self.ztnorm:
      self.setZTnormGroup(groups)

    i=0
    total=len(models)
    scores4 = torch.core.array.float64_1((4,))
    for c in models:
      scores=self.scores_client(c)
      scores4[0] = scores[0][4]
      scores4[1] = scores[1][4]
      for x in scores:
        output_file.write(str(x[2]) + " " + str(x[0]) + " " + str(x[3]) + " " + str(x[4]) + "\n") 

      scores=self.scores_impostor(c)
      scores4[2] = scores[0][4]
      scores4[3] = scores[1][4]
      for x in scores:
        output_file.write(str(x[2]) + " " + str(x[0]) + " " + str(x[3]) + " " + str(x[4]) + "\n") 
      
      i+=1
    
    return scores4


class TestTest(unittest.TestCase):
  """Performs various face recognition tests using the BANCA_SMALL database."""
  
  def test01_gmm_ztnorm(self):
    # Creates a temporary directory
    output_dir = tempfile.mkdtemp()
    # Get the directory where the features and the UBM are stored
    data_dir = os.path.join('data', 'bancasmall')
    
    # define some database-related variables 
    db = torch.db.banca_small.Database()
    protocol='P'
    extension='.hdf5'

    # create a subdirectory for the models
    models_dir = os.path.join(output_dir, "models")
    if not os.path.exists(models_dir):
      os.mkdir(models_dir)

    # loads the UBM model
    wm_path = os.path.join(data_dir, "ubmT5.hdf5")
    wm = torch.machine.GMMMachine(torch.io.HDF5File(wm_path))

    # creates a GMM experiments using Linear Scoring and ZT-norm
    exp = GMMExperiment(db, data_dir, extension, protocol, wm, models_dir, True, True)
    exp.iterg = 1
    exp.iterk = 50
    exp.convergence_threshold = 0.0005
    exp.variance_threshold = 0.001
    exp.relevance_factor = 4.
    exp.responsibilities_threshold = 0

    # creates a directory for the results
    result_dir=os.path.join(output_dir, "results", "")
    if not os.path.exists(result_dir):
      os.makedirs(result_dir)

    # Run the experiment
    scores=exp.run('dev', open(os.path.join(result_dir, 'scores-dev'), 'w'))

    # Check results (scores)
    scores_ref = torch.core.array.float64_1([2.073368737400600, 1.524833680242284, 
      2.468051383113884, 1.705402816531652], (4,))
    self.assertTrue( ((scores - scores_ref) < 1e-4).all() )

    # Remove output directory
    shutil.rmtree(output_dir)


if __name__ == '__main__':
  sys.argv.append('-v')
  if os.environ.has_key('TORCH_PROFILE') and \
      os.environ['TORCH_PROFILE'] and \
      hasattr(torch.core, 'ProfilerStart'):
    torch.core.ProfilerStart(os.environ['TORCH_PROFILE'])
  os.chdir(os.path.realpath(os.path.dirname(sys.argv[0])))
  unittest.main()
  if os.environ.has_key('TORCH_PROFILE') and \
      os.environ['TORCH_PROFILE'] and \
      hasattr(torch.core, 'ProfilerStop'):
    torch.core.ProfilerStop()
