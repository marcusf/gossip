"""
pagerank.py
Implements a basic page rank algorithm.

We use a simple hash table mapping URI's to a sparse
matrix, from which we calulate the Perron-Frobenius eigenvector,
using the standard page rank algorithm, normalized to [0,1].

Ideas:
  * Maybe decide on a canonical form for URL's, eg is either
	www.daringfireball.net or daringfireball.net the correct
	representation? Clearly a.blogspot.com and b.blogsspot.com
	differ, but x.com and www.x.com don't. Hm?
"""

import unittest
from numpy import linalg, ones, dot, array, abs, size, sum, allclose
from scipy import sparse

class Pagerank:
	"""Contains methods for building a pagerank graph and
	calculating its pagerank."""
	def __init__(self):
		self.urls = {}
		self.reversel = {}
		self.max_id = 0
		self.dim = 500
		self.normal_matrix = None
		self.links = sparse.lil_matrix((self.dim, self.dim))
		self.invalid = True
	
	def has_indexed(self, url):
		return self.urls.has_key(url)
	
	def index_of(self, url):
		"""True if the page rank is ranking the URL"""
		if self.urls.has_key(url):
			return self.urls[url]
		return None
		
	def url_of(self, index):
		"""Returns an URL associated with a certain index"""
		if index < len(self.reversel): return self.reversel[index]

	def insert(self, id):
		"""Inserts a URL in to the pagerank. Returns the ID
		of the inserted URL. If the URL is in the graph already,
		return that ID instead."""
		if not self.has_indexed(url):
			self.urls[url] = self.max_id
			self.reversel[self.max_id] = url
			self.max_id += 1
			# Reshape the matrix if we've filled it
			if self.max_id == self.dim:
				self.dim *= 2
				self.links = self.links.reshape((self.dim, self.dim))
		self.invalidate()
		return self.index_of(url)
		
	def invalidate(self):
		"""Marks the pagerank as invalid for the current setup"""
		self.invalid = True
		if self.normal_matrix: self.normal_matrix = None
	
			
	def link(self, from_url, to_url):
		"""Inserts a link in the graph from from_url to to_url"""
		self.invalidate()
		from_id = self.insert(from_url)
		to_id = self.insert(to_url)
		self.links[from_id,to_id] = 1.0
		
	def normalize_graph(self):
		"""Creates a normalized graph, i.e. makes a new graph for actually
		calculating the pagrank in, and gives columns equal values,
		and adds constant noise (the damping factor)"""
		# 1 - The damping factor of the graph
		DAMP = 0.85
		idx_max = self.max_id 
		self.normal_matrix = self.links[0:idx_max,0:idx_max]
		for i in range(0,idx_max):
			# Iterate along the column, since columns show outbound
			# links, and these are the ones we want to normalize
			col = self.normal_matrix[i,:].todense()
			col_nonzero = size(col[col>0])
			if col_nonzero > 0: col[col>0] = DAMP*1.0/col_nonzero
			else: col = DAMP*1/len(col)
			col = col + (1.0-DAMP)/idx_max
			self.normal_matrix[i,:] = col
		self.normal_matrix = self.normal_matrix.transpose()
	
	def get_rank(self):
		"""Calculates the pagerank."""
		# Get ourself a decent graph
		if self.invalid:
			self.normalize_graph()
		# Find the dominant eigenvector
		Vn = self.find_dominant(self.normal_matrix)
		# Process the result afterwards
		result = [float(x) for x in Vn]
		result = zip(range(0,len(result)),result)
		result.sort(lambda a,b: int(100000*(b[1]-a[1])))
		self.invalid = False
		return result
		
	def find_dominant(self, A):
		"""Finds the dominant eigenvector of matrix A.
		Since no method currently exist in SciPack for iteratively 
		finding	the dominant eigenvector (wich we know exist), we 
		calculate it by hand using the power method."""
		# Start by taking a random guess, we choose (1/n, ..., 1/n)'
		N = A.shape[0]
		V = sparse.lil_matrix((1,N))
		V[0,0:N] = ones((1,N)) * 1/N
		V = V.transpose()
		# Iterate until we get sufficient precision
		while True:
			Vn = self.iterate_once(A,V)
			if allclose(Vn.todense(), V.todense()): break
			V = Vn
		return Vn.todense()
		
	def iterate_once(self,A,V):
		"""Performs one iteration in the power method for approximating
		an eigenvector."""
		V =  A * V
		Vend = float(V[size(V)-1,0])
		return 1 / Vend * V

# ========================================================================
def tst_make_list():
	u = {}
	u['google'] = "http://google.se"
	u['goagrejor'] = "http://goagrejor.blogspot.com"
	u['idg'] = "http://www.idg.se"
	u['scipy'] = "http://www.scipy.org"
	u['enea'] = "http://www.enea.com"
	u['apple'] = "http://www.apple.com"
	return u
	
def tst_make_links(rank, u):
	[rank.insert(url) for url in u.values()]
	# Links from Goagrejor
	rank.link(u['goagrejor'], u['google'])
	rank.link(u['goagrejor'], u['enea'])
	rank.link(u['goagrejor'], u['apple'])
	# Links from IDG
	rank.link(u['idg'], u['google'])
	rank.link(u['idg'], u['goagrejor'])
	rank.link(u['idg'], u['enea'])
	rank.link(u['idg'], u['scipy'])
	# Links from Google
	rank.link(u['google'], u['enea'])
	rank.link(u['google'], u['google'])
	rank.link(u['google'], u['goagrejor'])
	rank.link(u['google'], u['idg'])
	rank.link(u['google'], u['scipy'])
	# Links from SCIPY
	rank.link(u['scipy'], u['enea'])
	# Links from ENEA
	rank.link(u['enea'], u['google'])
	rank.link(u['enea'], u['goagrejor'])
	rank.link(u['enea'], u['enea'])
	# Links from APPLE
	rank.link(u['apple'],u['idg'])
	
	return rank

class test_pagerank(unittest.TestCase):
	'''Tests for the page rank algorithm, and supporting
	sparse matrix and hash mapping.'''
	
	def setUp(self):
		self.pagerank = Pagerank()
		self.u = tst_make_list()
		
	def insert_values(self):
		'''Creates a fictious web to evaluate on.'''
		self.pagerank = Pagerank()
		self.pagerank = tst_make_links(self.pagerank, self.u)
		
	def test_insert(self):
		self.assertEqual(self.pagerank.insert('www.idg.se'),
		 self.pagerank.insert('www.idg.se'))
	
	def test_normalize(self):
		self.insert_values()
		self.pagerank.normalize_graph()
		return True
	
	def test_has_index(self):
		self.assert_(not self.pagerank.has_indexed('www.a.se'))
		self.pagerank.insert('www.a.se')
		self.assert_(self.pagerank.has_indexed('www.a.se'))
	
	def test_pagerank(self):
		self.insert_values()
		vector = self.pagerank.get_rank()
		list = [x[0] for x in vector]
		# Ordningen: ENEA, Google, Goagrejor, 
		#			 IDG, SciPy, Apple
		self.assertEqual(list,[4, 0, 2, 5, 3, 1])
		return True


if __name__ == '__main__':
	unittest.main()