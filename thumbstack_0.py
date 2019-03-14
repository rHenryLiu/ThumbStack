from headers import *

##################################################################################
##################################################################################

class ThumbStack(object):

#   def __init__(self, U, Catalog, pathMap="", pathMask="", pathHit="", name="test", nameLong=None, save=False, nProc=1):
   def __init__(self, U, Catalog, cmbMap, cmbMask, cmbHit, name="test", nameLong=None, save=False, nProc=1):
      
      self.nProc = nProc
      self.U = U
      self.Catalog = Catalog
      self.name = name
      if nameLong is None:
         self.nameLong = self.name
      else:
         self.nameLong = nameLong
      self.cmbMap = cmbMap
      self.cmbMask = cmbMask
      self.cmbHit = cmbHit
      
      # Output path
      self.pathOut = "./output/thumbstack/"+self.name
      if not os.path.exists(self.pathOut):
         os.makedirs(self.pathOut)

      # Figures path
      self.pathFig = "./figures/thumbstack/"+self.name
      if not os.path.exists(self.pathFig):
         os.makedirs(self.pathFig)
      # test figures path
      self.pathTestFig = self.pathFig+"/tests"
      if not os.path.exists(self.pathTestFig):
         os.makedirs(self.pathTestFig)

   
#      self.loadMaps(nProc=self.nProc)
      self.loadAPRadii()
      
      if save:
         self.saveOverlapFlag(nProc=self.nProc)
      self.loadOverlapFlag()
      
      if save:
         self.saveFiltering(nProc=self.nProc)
      self.loadFiltering()





   ##################################################################################
   ##################################################################################
   
   def loadAPRadii(self):
   
      # radii to use for AP filter: comoving Mpc/h
      self.nRAp = 4  #15
      
      # Aperture radii in Mpc/h
      self.rApMinMpch = 1.
      self.rApMaxMpch = 5
      self.RApMpch = np.linspace(self.rApMinMpch, self.rApMaxMpch, self.nRAp)
      
      # Aperture radii in arcmin
      self.rAnMinArcmin = 1.
      self.rAnMaxArcmin = 4.
      self.RApArcmin = np.linspace(self.rAnMinArcmin, self.rAnMaxArcmin, self.nRAp)


   ##################################################################################
   
   # check the hit map as a function of dec, at fixed ra = 0
   # this uses interpolation with the nearest pixels
   def sky2map(self, ra, dec, map):
      '''Gives the map value at coordinates (ra, dec).
      The value is interpolated between the nearest pixels.
      Will return 0 if the coordinates requested are outside the map
      '''
      # interpolate the map to the given sky coordinates
      sourcecoord = np.array([dec, ra]) * utils.degree
      # use nearest neighbor interpolation
      return map.at(sourcecoord, prefilter=False, mask_nan=False, order=0)
   
   
   ##################################################################################
   
   def saveOverlapFlag(self, nProc=1):
      print "Create overlap flag"
      # find if a given object overlaps with the CMB hit map
      def foverlap(iObj, thresh=1.e-5):
         '''Returns 1. if the object overlaps with the hit map and 0. otherwise.
         '''
         if iObj%100000==0:
            print "-", iObj
         ra = self.Catalog.RA[iObj]
         dec = self.Catalog.DEC[iObj]
         hit = self.sky2map(ra, dec, self.cmbHit)
         return np.float(hit>thresh)
      
#      overlapFlag = np.array(map(foverlap, range(self.Catalog.nObj)))
      tStart = time()
      with sharedmem.MapReduce(np=nProc) as pool:
         overlapFlag = np.array(pool.map(foverlap, range(self.Catalog.nObj)))
      tStop = time()
      print "took", (tStop-tStart)/60., "min"
      print "Out of", self.Catalog.nObj, "objects,", np.sum(overlapFlag), "overlap, ie a fraction", np.sum(overlapFlag)/self.Catalog.nObj
      np.savetxt(self.pathOut+"/overlap_flag.txt", overlapFlag)
   
   
   def loadOverlapFlag(self):
      self.overlapFlag = np.genfromtxt(self.pathOut+"/overlap_flag.txt")
   
   
   ##################################################################################
   
   def examineCmbMaps(self):
   
      # mask, before re-thresholding
      x = self.cmbMask.copy()
      path = self.pathFig+"/hist_cmbmask_prerethresh.pdf"
      myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'CMB mask value', semilogy=True)

      # rethreshold the mask
      mask = (self.cmbMask>0.5)[0]

      # mask, after re-thresholding
      x = mask.copy()
      path = self.pathFig+"/hist_cmbmask_postrethresh.pdf"
      myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'CMB mask value', semilogy=True)

      # masked map histogram
      x = self.cmbMap[mask]
      path = self.pathFig+"/hist_cmbmap.pdf"
      myHistogram(x, nBins=71, lim=(-10.*np.std(x), 10.*np.std(x)), path=path, nameLatex=r'CMB map value', semilogy=True, doGauss=True, S2Theory=[110.**2])

      # masked hit count histogram
      x = self.cmbHit[mask]
      path = self.pathFig+"/hist_cmbhit.pdf"
      myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'CMB hit count', semilogy=True)
   
   
   ##################################################################################
   

   def extractStamp(self, ra, dec, dxDeg=0.25, dyDeg=0.25, resArcmin=0.25, proj='cea', test=False):
      """Extracts a small CEA or CAR map around the given position, with the given angular size and resolution.
      """

      # define geometry of small square maps to be extracted
      # here 0.5deg * 0.5deg, with 0.25arcmin pixel
      # the center of the small square map will be specified later
      # car: not equal area, but equally-spaced coordinates
      # cea: equal area pixels, but coordinates are not equally spaced
      # previous kSZ paper: went out to 5arcmin
      # Planck paper CV: went out to 18 arcmin
      # --> let's go to 18'*sqrt(2) = 25' \simeq 0.5deg
      # probably good to extract bigger stamp than needed for now
      shape, wcs = enmap.geometry(np.array([[-0.5*dxDeg,-0.5*dyDeg],[0.5*dxDeg,0.5*dyDeg]])*utils.degree, res=resArcmin*utils.arcmin, proj=proj)
      stampMap = enmap.zeros(shape, wcs)
      stampMask = enmap.zeros(shape, wcs)
      stampHit = enmap.zeros(shape, wcs)

      # coordinates of the square map (between -1 and 1 deg)
      # output map position [{dec,ra},ny,nx]
      opos = stampMap.posmap()

      # coordinate of the center of the square map we want to extract
      # (known point source)
      # ra, dec in this order
      sourcecoord = np.array([ra, dec])*utils.degree

      # corresponding true coordinates on the big healpy map
      ipos = rotfuncs.recenter(opos[::-1], [0,0,sourcecoord[0],sourcecoord[1]])[::-1]

      # extract the small square map by interpolating the big healpy map
      # Here, I use nearest neighbor interpolation (order=0)
      # these are now numpy arrays: the wcs info is gone
      stampMap[:,:] = self.cmbMap.at(ipos, prefilter=False, mask_nan=False, order=0)
      stampMask[:,:] = self.cmbMask.at(ipos, prefilter=False, mask_nan=False, order=0)
      stampHit[:,:] = self.cmbHit.at(ipos, prefilter=False, mask_nan=False, order=0)
      
      # re-threshold the mask map, to keep 0 and 1 only
      stampMask[:,:] = 1.*(stampMask[:,:]>0.5)

      if test:
         print "Extracted cutouts around ra=", ra, "dec=", dec
         
         print "Map:"
         print "- min, mean, max =", np.min(stampMap), np.mean(stampMap), np.max(stampMap)
         print "- plot"
         plots=enplot.plot(stampMap, grid=True)
         enplot.write(self.pathTestFig+"/stampmap_ra"+np.str(np.round(ra, 2))+"_dec"+np.str(np.round(dec, 2)), plots)

         print "Mask:"
         print "- min, mean, max =", np.min(stampMask), np.mean(stampMask), np.max(stampMask)
         print "- plot"
         plots=enplot.plot(stampMask, grid=True)
         enplot.write(self.pathTestFig+"/stampmask_ra"+np.str(np.round(ra, 2))+"_dec"+np.str(np.round(dec, 2)), plots)

         print "Hit count:"
         print "- min, mean, max =", np.min(stampHit), np.mean(stampHit), np.max(stampHit)
         print "- plot the hit"
         plots=enplot.plot(stampHit, grid=True)
         enplot.write(self.pathTestFig+"/stamphit_ra"+np.str(np.round(ra, 2))+"_dec"+np.str(np.round(dec, 2)), plots)

      return opos, stampMap, stampMask, stampHit



   ##################################################################################

   def diskRingFilter(self, opos, stampMap, stampMask, stampHit, r0, r1, test=False):
      """Apply an AP filter (disk minus ring) to a stamp map:
      AP = int d^2theta * Filter * map.
      Unit is [map unit * sr]
      The filter is dimensionless:
      Filter = 1 in the disk, - (disk area)/(ring area) in the ring, 0 outside.
      Hence:
      int d^2theta * Filter = 0.
      r0 and r1 are the radius of the disk and ring in radians.
      """
      # coordinates of the square map (between -1 and 1 deg, or whatever the size is)
      # local coordinates in rad.
      # zero is at the center of the map
      # output map position [{dec,ra},ny,nx]
      dec = opos[0,:,:]
      ra = opos[1,:,:]
      radius = np.sqrt(ra**2 + dec**2)
      
      # disk filter [dimensionless]
      inDisk = 1.*(radius<=r0)
      # ring filter [dimensionless], normalized so that the disk-ring filter integrates exactly to zero
      inRing = 1.*(radius>r0)*(radius<=r1)
      inRing *= np.sum(inDisk) / np.sum(inRing)
      # disk minus ring filter [dimensionless]
      filter = inDisk - inRing
      
      # exact angular area of pixel [sr]
      pixArea = ra.area() / len(ra.flatten())
      # exact angular area of disk [sr]
      diskArea = np.sum(inDisk) * pixArea

      # apply the filter: int_disk d^2theta map -  disk_area / ring_area * int_ring d^2theta map
      filtMap = np.sum(pixArea * filter * stampMap)   # [map unit * sr]
      
      # detect point sources within the filter:
      # gives 0 in the absence of point sources/edges; gives >=1 in the presence of point sources/edges
      filtMask = np.sum((radius<=r1) * (1-stampMask))   # [dimensionless]
      
      # quantify noise std dev in the filter
      filtNoiseStdDev = np.sqrt(np.sum((pixArea * filter)**2 / stampHit)) # to get the std devs [sr / hit unit]


      if test:
         print "AP filter with disk radius =", r0 * (180.*60./np.pi), "arcmin"

         # count nb of pixels where filter is strictly positive
         nbPix = len(np.where(filter>0.)[0])
         print "- nb of pixels where filter>0: "+str(nbPix)
         print "- disk area: "+str(diskArea)+" sr, ie "+str(diskArea * (180.*60./np.pi)**2)+"arcmin^2"
         print "  (from r0, expect "+str(np.pi*r0**2)+" sr, ie "+str(np.pi*r0**2 * (180.*60./np.pi)**2)+"arcmin^2)"
         
         print "- disk-ring filter sums over pixels to "+str(np.sum(filter))
         print "  (should be 0; compared to "+str(len(filter.flatten()))+")"
         
         print "- filter on unit disk: "+str(np.sum(pixArea * filter * inDisk))
         print "  (should be disk area in sr: "+str(diskArea)+")"
         print "- filter on map: "+str(filtMap)
         print "- filter on mask: "+str(filtMask)
         print "- filter on inverse hit: "+str(filtNoiseStdDev)

         print "- plot the filter"
         filterMap = stampMap.copy()
         filterMap[:,:] = filter.copy()
         plots=enplot.plot(filterMap,grid=True)
         enplot.write(self.pathTestFig+"/stampfilter_r0"+floatExpForm(r0)+"_r1"+floatExpForm(r1), plots)

      return filtMap, filtMask, filtNoiseStdDev, diskArea


   ##################################################################################


   # analysis to be done for each object
   def analyzeObject(self, iObj, test=False):
      
      if iObj%1000==0:
         print "- analyze object", iObj
      
      # create arrays of filter values for the given object
      filtMap = np.zeros(self.nRAp)
      filtMask = np.zeros(self.nRAp)
      filtNoiseStdDev = np.zeros(self.nRAp)
      diskArea = np.zeros(self.nRAp)
      
      # only do the analysis if the object overlaps with the CMB map
      if self.overlapFlag[iObj]:
         # Object coordinates
         ra = self.Catalog.RA[iObj]   # in deg
         dec = self.Catalog.DEC[iObj] # in deg
         z = self.Catalog.Z[iObj]
         
         # extract postage stamp around it
         opos, stampMap, stampMask, stampHit = self.extractStamp(ra, dec, dxDeg=0.25, dyDeg=0.25, resArcmin=0.25, proj='cea', test=test)
         
         # loop over the radii for the AP filter
         for iRAp in range(self.nRAp):
            
#            # disk radius in comoving Mpc/h
#            rApMpch = self.RApMpch[iRAp]
#            # convert to radians at the given redshift
#            r0 = rApMpch / self.U.bg.comoving_transverse_distance(z) # rad


            # Disk radius in rad
            r0 = self.RApArcmin[iRAp] / 60. * np.pi/180.
            
            
            # choose an equal area AP filter
            r1 = r0 * np.sqrt(2.)
            
            
            
            # perform the filtering
            filtMap[iRAp], filtMask[iRAp], filtNoiseStdDev[iRAp], diskArea[iRAp] = self.diskRingFilter(opos, stampMap, stampMask, stampHit, r0, r1, test=test)

      return filtMap, filtMask, filtNoiseStdDev, diskArea



   def saveFiltering(self, nProc=1):
      
      # initialize arrays
      self.filtMap = np.zeros((self.Catalog.nObj, self.nRAp))
      self.filtMask = np.zeros((self.Catalog.nObj, self.nRAp))
      self.filtNoiseStdDev = np.zeros((self.Catalog.nObj, self.nRAp))
      self.diskArea = np.zeros((self.Catalog.nObj, self.nRAp))

      # loop over all objects in catalog
#      result = np.array(map(self.analyzeObject, range(self.Catalog.nObj)))
      tStart = time()
      with sharedmem.MapReduce(np=nProc) as pool:
         result = np.array(pool.map(self.analyzeObject, range(self.Catalog.nObj)))
      tStop = time()
      print "took", (tStop-tStart)/60., "min"
      
      # unpack and save to file
      self.filtMap = result[:,0,:].copy()
      np.savetxt(self.pathOut+"/filtmap.txt", self.filtMap)
      #
      self.filtMask = result[:,1,:].copy()
      np.savetxt(self.pathOut+"/filtmask.txt", self.filtMask)
      #
      self.filtNoiseStdDev = result[:,2,:].copy()
      np.savetxt(self.pathOut+"/filtnoisestddev.txt", self.filtNoiseStdDev)
      #
      self.diskArea = result[:,3,:].copy()
      np.savetxt(self.pathOut+"/diskarea.txt", self.diskArea)


   def loadFiltering(self):
      self.filtMap = np.genfromtxt(self.pathOut+"/filtmap.txt")
      self.filtMask = np.genfromtxt(self.pathOut+"/filtmask.txt")
      self.filtNoiseStdDev = np.genfromtxt(self.pathOut+"/filtnoisestddev.txt")
      self.diskArea = np.genfromtxt(self.pathOut+"/diskarea.txt")


   ##################################################################################


   def catalogMask(self, overlap=True, psMask=True, mVir=[1.e6, 1.e17], extraSelection=1.):
      '''Returns catalog mask: 1 for objects to keep, 0 for objects to discard.
      Use as:
      maskedQuantity = Quantity[mask]
      '''
      # Here mask is 1 for objects we want to keep
      mask = np.ones_like(self.Catalog.RA)
      #print "keeping fraction", np.sum(mask)/len(mask), " of objects"
      if mVir is not None:
         mask *= (self.Catalog.Mvir>=mVir[0]) * (self.Catalog.Mvir<=mVir[1])
         #print "keeping fraction", np.sum(mask)/len(mask), " of objects"
      if overlap:
         mask *= self.overlapFlag.copy()
         #print "keeping fraction", np.sum(mask)/len(mask), " of objects"
      # PS mask: look at largest aperture, and remove if any point within the disk or ring is masked
      if psMask:
         mask *= 1.*(np.abs(self.filtMask[:,-1])<1.)
         #print "keeping fraction", np.sum(mask)/len(mask), " of objects"
      mask *= extraSelection
      #print "keeping fraction", np.sum(mask)/len(mask), " of objects"

      mask = mask.astype(bool)
      #print "keeping fraction", np.sum(mask)/len(mask), " of objects"
      return mask


   ##################################################################################

   def stack(self, quantity, mask, weights, norm=True):
      '''Stacks the quantity for the objects selected by mask,
      applying weights from weight.
      The quantity can be a single value per object, or an array for each object,
      like e.g. self.filtMap.
      Norm=True if you want to normalize by the sum of the weights.
      '''
      result = np.sum(quantity[mask,:] * weights[mask,np.newaxis], axis=0)
      if norm:
         result /= np.sum(weights[mask,np.newaxis], axis=0)
      return result


   def plotStack(self, stack, stackError=None, ylim=None, name='dT', nameLatex=r'$\delta T$ [$\mu$K]' ):
      """Generic stack plotter.
      """
      fig=plt.figure(0)
      ax=fig.subplot(111)
      #
      if stackError is None:
         ax.plot(self.RApMpch, stack, 'o-')
      else:
         ax.errorbar(self.RApMpch, stack, yerr=stackError, fmt='o-')
      #
      ax.set_xlabel(r'$R$ [cMpc/h]')
      ax.set_ylabel(nameLatex)
#      fig.savefig(self.pathFig+"/stack_"+name+".pdf")
#      fig.clf()
      plt.show()


   ##################################################################################


   def measureVarFromHitCount(self):
      """Returns a list of functions, one for each AP filter radius,
      where the function takes filtNoiseStdDev**2 as input and returns the
      actual measured filter variance.
      To be used for noise weighting in the stacking
      """
      # keep only objects that overlap, and mask point sources
      mask = self.catalogMask(overlap=True, psMask=True)
   
      fVarFromHitCount = []
      for iRAp in range(self.nRAp):
         x = self.filtNoiseStdDev[mask, iRAp]**2
         y = self.filtMap[mask, iRAp].copy()
         y = (y - np.mean(y))**2

         # define bins
         nBins = 21
         BinsX = np.logspace(np.log10(np.min(x)), np.log10(np.max(x)), nBins, 10.)
         
         # compute histograms
         binCenters, binEdges, binIndices = stats.binned_statistic(x, x, statistic='mean', bins=BinsX)
         binCounts, binEdges, binIndices = stats.binned_statistic(x, x, statistic='count', bins=BinsX)
         binnedVar, binEdges, binIndices = stats.binned_statistic(x, y, statistic=np.mean, bins=BinsX)
         sBinnedVar, binEdges, binIndices = stats.binned_statistic(x, y, statistic=np.std, bins=BinsX)
         sBinnedVar /= np.sqrt(binCounts)
         
         # interpolate, to use as noise weighting
         fVarFromHitCount.append( interp1d(binCenters, binnedVar, kind='linear', bounds_error=False, fill_value=(binnedVar[0],binnedVar[-1])) )

         # plot
         fig=plt.figure(0)
         ax=fig.add_subplot(111)
         #
         # measured
         ax.errorbar(binCenters, binnedVar, yerr=sBinnedVar, fmt='.', label=r'measured')
         #
         # interpolated
         newX = np.logspace(np.log10(np.min(x)/2.), np.log10(np.max(x)*2.), 10.*nBins, 10.)
         newY = np.array(map(fVarFromHitCount[iRAp], newX))
         ax.plot(newX, newY, label=r'interpolated')
         #
         ax.set_xscale('log', nonposx='clip')
         ax.set_yscale('log', nonposy='clip')
         #
         path = self.pathFig+"/binned_noise_vs_hit"+str(iRAp)+".pdf"
         fig.savefig(path, bbox_inches='tight')
         fig.clf()

      return fVarFromHitCount


   ##################################################################################



   def examineHistograms(self, fsAp=[]):
      """fsAp is an optional list of functions of rAp in radians, which return the expected std def of the AP filter
      """
      
#      self.catalogMask(overlap=True, psMask=True, mVir=[1.e6, 1.e17], extraSelection=1.)
#      path = self.pathFig+"/hist_x.pdf"
#      myHistogram(DEC[mask], nBins=71, lim=(-90., 90.), path=path, nameLatex=r'$x$ [km/s]', semilogx=False, doGauss=False)

      # first, keep all objects that overlap, even the masked ones
      mask = self.catalogMask(overlap=True, psMask=False)

      # check that the non-overlapping objects are the ones with the correct DEC
      path = self.pathFig+"/hist_dec_overlap.pdf"
      myHistogram(self.Catalog.DEC[mask], nBins=71, lim=(-30., 90.), path=path, nameLatex=r'Dec [deg]')
      
      # check the values of the filters on the point source mask, to find a relevant cut
      # look at the largest aperture
      x = self.filtMask[mask,-1]
      path = self.pathFig+"/hist_psmaskvalue_before.pdf"
      myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'PS mask value', semilogy=True)
      
      # then  remove the objects that overlap with point sources
      mask = self.catalogMask(overlap=True, psMask=True)

      # redo the mask histogram, to check
      x = self.filtMask[mask,-1]
      path = self.pathFig+"/hist_psmaskvalue_after.pdf"
      myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'PS mask value', semilogy=True)
      
      # Histograms of filter outputs
      for iRAp in range(self.nRAp):
         x = self.filtMap[mask, iRAp]
         path = self.pathFig+"/hist_filtvalue"+str(iRAp)+".pdf"
         S2Theory = []
         for f in fsAp:
            # theory assumes int d^2theta W = 1
            s2Theory = f(self.RApArcmin[iRAp] * np.pi/180./60.)**2
            # so multiply by disk area, but it can vary from object to object
            # we neglect this source of scatter and just keep the mean
            s2Theory *= np.mean(self.diskArea[mask, iRAp])**2
            S2Theory.append(s2Theory)
         myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'AP filter value', S2Theory=S2Theory, doGauss=True, semilogy=True)

   
      # Histograms of noise std dev, from hit counts
      for iRAp in range(self.nRAp):
         x = self.filtNoiseStdDev[mask, iRAp]
         path = self.pathFig+"/hist_noisestddevhit"+str(iRAp)+".pdf"
         myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'Std dev value [arbitrary]', semilogy=True)


      # tSZ / dust
      for iRAp in range(self.nRAp):
         weights = 1. / self.filtNoiseStdDev[mask, iRAp]**2   # need inverse variance, not std dev
         weights /= np.mean(weights)   # to keep the size and units of the weighted AP outputs
         x = self.filtMap[mask, iRAp] * weights
         print "- mean tSZ= "+str(np.mean(x))+"; std on mean= "+str(np.std(x)/np.sqrt(len(x)))+"; SNR= "+str(np.mean(x)/np.std(x)*np.sqrt(len(x)))
         path = self.pathFig+"/hist_tsz"+str(iRAp)+".pdf"
         myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'Std dev value [arbitrary]', semilogy=True)
   
   
      """
      # kSZ: T * v / s2
      kSZ1 = np.zeros(self.nRAp)
      skSZ1 = np.zeros(self.nRAp)
      for iRAp in range(self.nRAp):
         # inverse-variance weighted fit for the slope of the dT-v relation
         num = np.sum(self.filtMap[mask, iRAp] * self.Catalog.vR[mask] / self.filtNoiseStdDev[mask, iRAp]**2)
         denom = np.sum(self.Catalog.integratedKSZ[mask] * self.Catalog.vR[mask] / self.filtNoiseStdDev[mask, iRAp]**2)
         
#         x = self.filtMap[mask, iRAp] * self.Catalog.vR[mask] / self.filtNoiseStdDev[mask, iRAp]**2
#         x /= np.mean(self.Catalog.integratedKSZ[mask] * self.Catalog.vR[mask] / self.filtNoiseStdDev[mask, iRAp]**2)
         #
         kSZ1[iRAp] = num / denom   #np.mean(x)
         skSZ1[iRAp] = 1. / np.sqrt(denom)   #np.std(x) / np.sqrt(len(x))
         print "- mean kSZ= "+str(kSZ1[iRAp])+"; std on mean= "+str(skSZ1[iRAp])+"; SNR= "+str(kSZ1[iRAp]/skSZ1[iRAp])
         path = self.pathFig+"/hist_ksz1"+str(iRAp)+".pdf"
         myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'kSZ fit', doGauss=True, semilogy=True)
      
      # kSZ: T * Mh * v / s2
      kSZ2 = np.zeros(self.nRAp)
      skSZ2 = np.zeros(self.nRAp)
      for iRAp in range(self.nRAp):
         # inverse-variance weighted fit for the slope of the dT-v relation
         num = np.sum(self.filtMap[mask, iRAp] * self.Catalog.integratedKSZ[mask] / self.filtNoiseStdDev[mask, iRAp]**2)
         denom = np.sum(self.Catalog.integratedKSZ[mask]**2 / self.filtNoiseStdDev[mask, iRAp]**2)
         
#         x = self.filtMap[mask, iRAp] * self.Catalog.integratedKSZ[mask] / self.filtNoiseStdDev[mask, iRAp]**2
#         x /= np.mean(self.Catalog.integratedKSZ[mask]**2 / self.filtNoiseStdDev[mask, iRAp]**2)
         #
         kSZ2[iRAp] = num / denom   #np.mean(x)
         skSZ2[iRAp] = 1. / np.sqrt(denom)   #np.std(x) / np.sqrt(len(x))
         print "- mean kSZ= "+str(kSZ2[iRAp])+"; std on mean= "+str(skSZ2[iRAp])+"; SNR= "+str(kSZ2[iRAp]/skSZ2[iRAp])
         path = self.pathFig+"/hist_ksz2"+str(iRAp)+".pdf"
         myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'kSZ fit', doGauss=True, semilogy=True)


      # kSZ: T * Mh * v / s2, subtracting the mean T and mean expected kSZ
      kSZ3 = np.zeros(self.nRAp)
      skSZ3 = np.zeros(self.nRAp)
      for iRAp in range(self.nRAp):
         # inverse-variance weighted fit for the slope of the dT-v relation
         t = self.filtMap[mask, iRAp] - np.mean(self.filtMap[mask, iRAp])
         k = self.Catalog.integratedKSZ[mask] - np.mean(self.Catalog.integratedKSZ[mask])
         s2Hit = self.filtNoiseStdDev[mask, iRAp]**2
         s2True = fVarFromHitCount[iRAp](self.filtNoiseStdDev[mask, iRAp]**2)
         
         num = np.sum(t * k / s2Hit)
         denom = np.sum(k**2 / s2Hit)
         s2num = np.sum(s2True * (k / s2Hit)**2)
         
#         x = t * k / self.filtNoiseStdDev[mask, iRAp]**2
#         x /= np.mean(k**2 / self.filtNoiseStdDev[mask, iRAp]**2)
         #
         kSZ3[iRAp] = num / denom   #np.mean(x)
         skSZ3[iRAp] = np.sqrt(s2num / denom**2)   #np.std(x) / np.sqrt(len(x))
         print "- mean kSZ= "+str(kSZ3[iRAp])+"; std on mean= "+str(skSZ3[iRAp])+"; SNR= "+str(kSZ3[iRAp]/skSZ3[iRAp])
         path = self.pathFig+"/hist_ksz3"+str(iRAp)+".pdf"
         myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'kSZ fit', doGauss=True, semilogy=True)


      # kSZ: T * Mh * v / s2, subtracting the mean T and mean expected kSZ,
      # and using the correct noise weighting
      kSZ4 = np.zeros(self.nRAp)
      skSZ4 = np.zeros(self.nRAp)
      fVarFromHitCount = self.measureVarFromHitCount()
      for iRAp in range(self.nRAp):
         # inverse-variance weighted fit for the slope of the dT-v relation
         t = self.filtMap[mask, iRAp] - np.mean(self.filtMap[mask, iRAp])
         k = self.Catalog.integratedKSZ[mask] - np.mean(self.Catalog.integratedKSZ[mask])
         s2True = fVarFromHitCount[iRAp](self.filtNoiseStdDev[mask, iRAp]**2)
         
         num = np.sum(t * k / s2True)
         denom = np.sum(k**2 / s2True)
         
#         x = t * k / s2
#         x /= np.mean(k**2 / s2)
         #
         kSZ4[iRAp] = num / denom   #np.mean(x)
         skSZ4[iRAp] = 1. / np.sqrt(denom)   #np.std(x) / np.sqrt(len(x))
         print "- mean kSZ= "+str(kSZ4[iRAp])+"; std on mean= "+str(skSZ4[iRAp])+"; SNR= "+str(kSZ4[iRAp]/skSZ4[iRAp])
         path = self.pathFig+"/hist_ksz4"+str(iRAp)+".pdf"
         myHistogram(x, nBins=71, lim=(np.min(x), np.max(x)), path=path, nameLatex=r'kSZ fit', doGauss=True, semilogy=True)

      """





   def measureKSZ(self):

      kSZ1 = np.zeros(self.nRAp)
      skSZ1 = np.zeros(self.nRAp)
      kSZ2 = np.zeros(self.nRAp)
      skSZ2 = np.zeros(self.nRAp)
      kSZ3 = np.zeros(self.nRAp)
      skSZ3 = np.zeros(self.nRAp)
      kSZ4 = np.zeros(self.nRAp)
      skSZ4 = np.zeros(self.nRAp)

      fVarFromHitCount = self.measureVarFromHitCount()
      for iRAp in range(self.nRAp):
         t = self.filtMap[mask, iRAp]# - np.mean(self.filtMap[mask, iRAp])
         v = - self.Catalog.vR[mask]# + np.mean(self.Catalog.vR[mask])
         k = self.Catalog.integratedKSZ[mask]# - np.mean(self.Catalog.integratedKSZ[mask])
         s2True = fVarFromHitCount[iRAp](self.filtNoiseStdDev[mask, iRAp]**2)
         s2Hit = self.filtNoiseStdDev[mask, iRAp]**2


         # kSZ1: T * v / s2Hit
         num = np.sum(t * v / s2Hit)
         denom = np.sum(k * v / s2Hit)
         s2num = np.sum(s2True * (v / s2Hit)**2)
         #
         kSZ1[iRAp] = num / denom
         skSZ1[iRAp] = np.sqrt(s2num / denom**2)

         # kSZ2: T * Mh v / s2Hit
         num = np.sum(t * k / s2Hit)
         denom = np.sum(k**2 / s2Hit)
         s2num = np.sum(s2True * (k / s2Hit)**2)
         #
         kSZ2[iRAp] = num / denom
         skSZ2[iRAp] = np.sqrt(s2num / denom**2)


         # subtracting mean
         t = self.filtMap[mask, iRAp] - np.mean(self.filtMap[mask, iRAp])
         k = self.Catalog.integratedKSZ[mask] - np.mean(self.Catalog.integratedKSZ[mask])
         s2True = fVarFromHitCount[iRAp](self.filtNoiseStdDev[mask, iRAp]**2)
         s2Hit = self.filtNoiseStdDev[mask, iRAp]**2

         # kSZ3: T * Mh v / s2Hit, subtracting mean
         num = np.sum(t * k / s2Hit)
         denom = np.sum(k**2 / s2Hit)
         s2num = np.sum(s2True * (k / s2Hit)**2)
         #
         kSZ3[iRAp] = num / denom
         skSZ3[iRAp] = np.sqrt(s2num / denom**2)

         # kSZ4: T * Mh v / s2Hit, subtracting mean,
         # and using the measured noise weights
         num = np.sum(t * k / s2True)
         denom = np.sum(k**2 / s2True)
         #
         kSZ4[iRAp] = num / denom
         skSZ4[iRAp] = np.sqrt(1. / denom)








      
      
      fig=plt.figure(0)
      ax=fig.add_subplot(111)
      #
      #self.RApMpch
      ax.errorbar(self.RApArcmin, kSZ1, skSZ1, label=r'$Tv/\sigma^2$')
      ax.errorbar(self.RApArcmin+0.01, kSZ2, skSZ2, label=r'$TMv/\sigma^2$')
      ax.errorbar(self.RApArcmin+0.02, kSZ3, skSZ3, label=r'$TMv/\sigma^2$, sub. T,Mv')
      ax.errorbar(self.RApArcmin+0.03, kSZ4, skSZ4, label=r'$TMv/\sigma^2$, sub. T,Mv, better noise')
      #
      ax.legend(loc=2, fontsize='x-small', labelspacing=0.1)
      ax.set_xlabel(r'$R$ [arcmin]')
      ax.set_ylabel(r'$\alpha_\text{kSZ}$')
      ax.set_ylim((0., 2.5))
      #
      # extra abscissa: disk radius in comoving Mpc/h
      ax2 = ax.twiny()
      ticks = ax.get_xticks()
      ax2.set_xticks(ticks)
      newticks = np.array(ticks) * np.pi/(180.*60.) * self.U.bg.comoving_distance(np.mean(self.Catalog.Z[mask]))  # disk radius in Mpc/h
      newticks = np.round(newticks, 2)
      ax2.set_xticklabels(newticks)
      ax2.set_xlim(ax.get_xlim())
      ax2.set_xlabel(r'$R$ [cMpc/h]', fontsize=20)
      ax2.xaxis.set_label_coords(0.5, 1.1)
      #
      # extra ordinate: signal in muK * arcmin^2
      ax3 = ax.twinx()
      ticks = ax.get_yticks()
      ax3.set_yticks(ticks)
      newticks = np.array(ticks) * np.mean(self.Catalog.integratedKSZ[mask]) * (180.*60./np.pi)**2 # [muK*arcmin^2]
      #newticks = np.round(newticks, 2)
      ax3.set_yticklabels(newticks)
      ax3.set_ylim(ax.get_ylim())
      ax3.set_ylabel(r'$\langle T_\text{kSZ} \rangle$ [$\mu$K.arcmin$^2$]', fontsize=20)
      ax3.yaxis.set_label_coords(1.1, 0.5)
      #
      path = self.pathFig+"/ksz.pdf"
      fig.savefig(path, bbox_inches='tight')
      fig.clf()














