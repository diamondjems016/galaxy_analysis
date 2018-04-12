from galaxy_analysis.plot.plot_styles import *
import yt
import numpy as np
from copy import copy
import sys
import deepdish as dd
from scipy.optimize import brentq
from galaxy_analysis.utilities import utilities

from galaxy_analysis.utilities import functions

import matplotlib.pyplot as plt

from scipy import integrate
from scipy.stats import distributions  # may not need
from scipy import stats

def gather_time_series(datafile, dsarray, phase, field, centers = None):

    if 'over' in field:
        cname = 'abins'
    else:
        cname = 'bins'

    i = 0
    ldata = {dsarray[0]: dd.io.load(datafile, "/" + dsarray[0])}
    data  = load_distribution_data(ldata, dsarray[0], phase, field, centers = cname)
    time_series = {}
    for k in data.keys():
        if k == 'hist':
            continue
        time_series[k] = np.zeros(np.size(dsarray))

    for dsname in dsarray:
        ldata = {dsname : dd.io.load(gas_file, "/" + dsname)}

        data  = load_distribution_data(ldata, dsname, phase, field, centers = cname)

        for k in data.keys():
            if k == 'hist':
                continue
            time_series[k][i] = data[k]

        i = i + 1

    return time_series


def plot_time_evolution(datafile, dsarray, denominator = None):
    """
    Make a panel plot showing the evolution of:
        Median abundance           : top row
        log(median) - log(average) : middle row
        q90 - q10                  : bottom row
    For the following elements as columns (7):
        Ba, Sr, Fe, Mn, Mg, O, N

    Either as mass fractions (denominator = None) or as abundance
    ratios (e.g. denominator = "Fe")
    """

    all_phases = ['Molecular','CNM','WNM','WIM','HIM']
    elements   = ['Ba','Sr','Fe','Mn','Mg','N','O']

    all_time_data = {}
    for e in elements:
        all_time_data[e] = {}


        if denominator is None:
            field = e + '_Fraction'
        elif e == denominator:
            continue # skip
        else:
            field = e + '_over_' + denominator

        for phase in all_phases:
            all_time_data[e][phase] =\
              gather_time_series(datafile, dsarray, phase, field)


    nrow = 3
    ncol = 7

    fig, ax = plt.subplots(nrow,ncol)
    fig.set_size_inches(nrow*6,ncol*6)

    axi = 0
    axj = 0

    times = np.arange(0, np.size(dsarray), 1) * 5

    color = {'Molecular' : 'C1', 'CNM' : 'C0', 'WNM' : 'C2', 'WIM':'C4','HIM' : 'C3'}

    for e in elements:


        for phase in all_phases:

            median = all_time_data[e][phase]['median']
            mean   = all_time_data[e][phase]['mean']
            d9d1   = all_time_data[e][phase]['q90_q10_range']

            ax[(0,axj)].plot(times, median, lw = 3, color = color[phase], ls = '-')
            ax[(1,axj)].plot(times, median - mean, lw = 3, color = color[phase], ls = '-')
            ax[(2,axj)].plot(times, d9d1, lw = 3, color = color[phase], ls = '-')

            if not (denominator is None):
                ax[(0,axj)].set_ylim(-8,0)
                ax[(1,axj)].set_ylim(0, 1)
                ax[(2,axj)].set_ylim(0, 3)

        for i in [0,1,2]:
            ax[(i,axj)].set_xlim(0, 500.0)

        axj = axj + 1

    ax[(0,0)].set_ylabel('Median (dex)')
    ax[(1,0)].set_ylabel('Med - Mean (dex)')
    ax[(2,0)].set_ylabel('d9 - d1 (dex)')

    fig.subplots_adjust(hspace = 0)
    fig.savefig('time_evolution.png')

    plt.close()
    
    return



def load_distribution_data(ldata, dsname, phase, field, centers = None):
    """
    Extracts some information from the dataset
    """
    rdata  = ldata[dsname][phase]['mass_fraction'][field]
    y      = ldata[dsname][phase]['mass_fraction'][field]['hist']
    mean   = ldata[dsname][phase]['mass_fraction'][field]['mean']
    std    = ldata[dsname][phase]['mass_fraction'][field]['std']
    q1     = ldata[dsname][phase]['mass_fraction'][field]['Q1']
    q3     = ldata[dsname][phase]['mass_fraction'][field]['Q3']
    q10    = ldata[dsname][phase]['mass_fraction'][field]['decile_1']
    q90    = ldata[dsname][phase]['mass_fraction'][field]['decile_9']

    if not (centers is None):

        if not (np.size(centers) == np.size(y)):
            if centers == 'bins':
                bins = ldata[dsname][phase]['mass_fraction'][centers]
            elif centers == 'abins':
                bins = ldata[dsname][phase]['mass_fraction'][centers]

            centers = 0.5 * (bins[1:] + bins[:-1])

    if rdata['Q3'] is None or rdata['Q1'] is None:
        rdata['iqr']           = None
        rdata['q90_q10_range'] = None
    else:

        if (q1 > 0 and q3 > 0 and q10 > 0 and q90 > 0) and (not 'over' in field):
            # safe to assume these are not logged data if all positive
            rdata['iqr']    = np.log10(q3) - np.log10(q1) # ldata[dsname][phase]['mass_fraction'][field]['inner_quartile_range']
            rdata['q90_q10_range'] = np.log10(q90) - np.log10(q10)
        else:
            rdata['iqr'] = q3 - q1
            rdata['q90_q10_range'] = q90 - q10

    rdata['label']  = ldata[dsname]['general']['Time']
    rdata['median'] = np.interp(0.5, np.cumsum(y)/(1.0*np.sum(y)), centers)
    if not 'over' in field:
        rdata['median'] = np.log10(rdata['median'])


    return rdata


def fit_multifunction_PDF(bins, y, data):
    """
    Fit lognormal + power law
    """

    success = {}
    rdict   = {}

    centers = 0.5 * (bins[1:] + bins[:-1])

    def _error(yfitvals, yvals):
        return np.sum( np.abs(yvals[yvals>0] - yfitvals[yvals>0])**2/yvals[yvals>0] )

    # lognormal
    try:
        lognormal_alone = fit_PDF(bins*1.0, y*1.0, data = data, function_to_fit = 'log-normal')
        success['lognormal'] = True
        lognormal_alone['error'] = _error( lognormal_alone['fit_function']._f(centers, *lognormal_alone['popt']) , lognormal_alone['norm_y'])
        rdict['lognormal']   = lognormal_alone
    except RuntimeError:
        success['lognormal'] = False

    # lognormal powerlaw
    ln_pl = fit_PDF(bins*1.0, y*1.0, data=data, function_to_fit = 'lognormal_powerlaw')
    success['lognormal_powerlaw'] = True
    ln_pl['error'] = _error(ln_pl['fit_function']._f(centers, *ln_pl['popt']) , ln_pl['norm_y'])
    rdict['lognormal_powerlaw'] = ln_pl

    if False: #try:
        gau_pl = fit_PDF(bins*1.0, y*1.0, data=data, function_to_fit = 'gaussian_powerlaw')
        success['gaussian_powerlaw'] = True
        gau_pl['error'] = _error(gau_pl['fit_function']._f(centers, *gau_pl['popt']), gau_pl['norm_y'])
        rdict['gaussian_powerlaw'] = gau_pl	
    #except RuntimeError:
    #    success['gaussian_powerlaw'] = False

    # powerlaw
    try:
        powerlaw_alone  = fit_PDF(bins, y, data = data, function_to_fit = 'powerlaw')
        success['powerlaw'] = True
#    powerlaw_alone['error'] = _error(powerlaw_alone['fit_function']._f( centers[centers>centers[np.argmax(powerlaw_alone['norm_y'])]] , *powerlaw_alone['popt']) ,
#                                         powerlaw_alone['norm_y'][ centers > centers[np.argmax(powerlaw_alone['norm_y'])]]  )
        powerlaw_alone['error'] = _error(powerlaw_alone['fit_function']._f( centers, *powerlaw_alone['popt']), powerlaw_alone['norm_y'])
        rdict['powerlaw'] = powerlaw_alone
    except RuntimeError:
        success['powerlaw'] = False

    # truncated powerlaw
    #truncated_powerlaw  = fit_PDF(bins, y, data = data, function_to_fit = 'truncated_powerlaw')
    #success['truncated_powerlaw'] = True
    #truncated_powerlaw['error'] = _error(truncated_powerlaw['fit_function']._f( centers , *truncated_powerlaw['popt']) ,
    #                                     truncated_powerlaw['norm_y'])
    #rdict['truncated_powerlaw'] = truncated_powerlaw

#    if all([not success[k] for k in success.keys()]):
#        print "Cannot find a fit"
#        raise ValueError

    min_error = np.inf
    for k in success.keys():

        if success[k]:
            rdict[k]['name'] = k
            if rdict[k]['error'] < min_error:
                min_error = rdict[k]['error']
                min_key   = k

    return rdict[min_key]

def fit_PDF(bins, y, data = None, function_to_fit = None, p0 = None, bounds = None,
                     fit_method = 'curve_fit', remove_residual = None):
    """
    fit_function is either a function object from utilities.functions OR
    the name of one of these functions
    """

    centers = 0.5 * (bins[1:] + bins[:-1])
    binsize = (bins[1:] - bins[:-1])

    norm_y = y / binsize
    if not (remove_residual is None):
        norm_y = norm_y - remove_residual

    # if data is provided we can do some cool things
    if p0 is None:
        if not (data is None):
            if function_to_fit == 'log-normal' or function_to_fit == 'lognormal_powerlaw':
                u_guess   = np.log( data['mean'] / (np.sqrt(1.0 + data['std']**2 / (data['mean']**2))))
                std_guess = np.sqrt( np.log(1.0 + data['std']**2 / data['mean']**2))

                p0 = [u_guess, std_guess]
                bounds = ( [p0[0]*1.0 - 10, 0.0], [p0[0]*1.0+10, 30.0])


            if function_to_fit == 'lognormal_powerlaw':
                 p0 = [u_guess - 3, 2.0, np.sqrt(-0.5 * (u_guess - 3 - np.log(data['mean'])))  ]
                 bounds = ( [p0[0] - 5, 1.0, 0.01], [u_guess+3, 20.0, 10.0])

        if function_to_fit == 'powerlaw' or function_to_fit == 'truncated_powerlaw':
            p0     = [2, 1.0E-5]
            bounds = ( [1.0,0], [np.inf,1.0])

        if function_to_fit == 'truncated_powerlaw':
            p0      = [p0[0]*1,p0[1]*1, centers[np.max([np.argmax(norm_y)-1,0])] ]
            bounds  = ([bounds[0][0]*1, 1*bounds[0][1], centers[np.max([np.argmax(norm_y)-10,0])]],
                                                        [1*bounds[1][0],1*bounds[1][1],centers[np.min([np.argmax(norm_y)+20,np.size(centers)-1])]])
        if function_to_fit == 'gaussian_powerlaw':
            p0     = [data['mean'], 2.0, data['std']]
            bounds = [ (p0[0]/100.0, 0.01, p0[2] / 1000.0), (p0[0]*100.0, 10.0, p0[2]*100.0)]

    # choose the region to fit over
    #   for all, this will be where there is data

    selection = (norm_y > 0)
#    if function_to_fit == 'log-normal':
#        selection = selection * (centers > 10.0**(np.log10(centers[np.argmax(norm_y)]) - 1.0)  )*\
#                                (centers < 10.0**(np.log10(centers[np.argmax(norm_y)]) + 1.0)  )
#    elif function_to_fit == 'powerlaw':
#        selection = selection * ( centers > centers[np.argmax(norm_y)] )  # Fit everything to the right of the peak


    x_to_fit = centers[selection]
    y_to_fit = norm_y[selection]

    # set fitting function
    if isinstance(function_to_fit, str):
        function_to_fit= functions.by_name[function_to_fit]()


    if function_to_fit.name == 'lognormal_powerlaw' or function_to_fit.name == 'gaussian_powerlaw':
        function_to_fit.full_mean = data['mean']

    # If we are using KS test to fit, then need to compute the CDF from the data
    if fit_method == 'KS':
        data_cdf  = np.cumsum(y[selection])
    else:
        data_cdf  = None

    # Fit -
    popt, pcov = function_to_fit.fit_function(x_to_fit, y_to_fit, p0 = p0,
                                              bounds = bounds, method = fit_method,
                                              data_cdf = data_cdf)

    fit_dictionary = {'popt' : copy(popt), 'pcov': copy(pcov),
                      'fit_function' : function_to_fit, 'norm_y' : norm_y*1.0,
                      'fit_x' : x_to_fit*1.0, 'fit_y' : y_to_fit*1.0,
                      'fit_result' : lambda xx : function_to_fit._f(xx, *popt) }

    return fit_dictionary

colors = ['C' + str(i) for i in [0,1,2,4,5,6,7,8,9]]
lss     = ['-','--']

def plot_all_elements(data, dsname, phase, elements = None, **kwargs):

    if elements is None:
        elements = ['Ba','Y','As','Sr','Mn','Na','Ca','N','Ni','Mg','S','Si','Fe','C','O']

    elements = ['Ba', 'Sr', 'Fe', 'Mn', 'Mg', 'O', 'N']

    fig, ax = plt.subplots(2)
    fig.set_size_inches(24,16)

    bins    = data[dsname][phase]['mass_fraction']['bins']
    centers = 0.5 * (bins[1:]+ bins[:-1])


#    sort   = np.argsort(ymax_order)
#    sort_e = np.array(elements)[sort]

    label_pos = np.empty((np.size(elements),))
    label_pos[::2] = 1
    label_pos[1::2] = -1

#    label_pos = label_pos[sort]

    ci = li = 0
    for i, e in enumerate(elements):
        field = e + '_Fraction'

        ds_data = load_distribution_data(data, dsname, phase, field, centers = centers) # subselect

        fit_dict = fit_multifunction_PDF(1.0*bins, 1.0*ds_data['hist'], ds_data)
                   #fit_PDF(bins, ds_data['hist'], data = ds_data, **kwargs)


        plot_histogram(ax[0], np.log10(bins), fit_dict['norm_y']/np.max(fit_dict['norm_y']),
                                    color = colors[ci], ls = lss[li], lw = line_width)

        ax[0].plot(np.log10(centers),
                   #np.log10(fit_dict['fit_x']), 
                   fit_dict['fit_result'](centers) / np.max(fit_dict['norm_y']),
                                      lw = line_width, ls = lss[li], color = colors[ci])


        select = fit_dict['norm_y'] > 0
        chisqr = (fit_dict['fit_result'](centers[select]) - fit_dict['norm_y'][select])**2 / fit_dict['norm_y'][select]
        error  = np.abs(fit_dict['fit_result'](centers[select]) - fit_dict['norm_y'][select]) / fit_dict['norm_y'][select]

        ax[1].plot(np.log10(centers[select]), error, lw = line_width, ls = lss[li], color = colors[ci])


####
        xtext = np.log10(centers[np.argmax(fit_dict['norm_y'])]) - 0.1 - 0.05
        xa    = np.log10(centers[np.argmax(fit_dict['norm_y'])])
        ya    = 1.0
        pos = label_pos[i]
        if pos > 0:
            xtext = xtext + 0.05
            ytext = 2.0
        xy = (xtext, ytext)
        xya = (xa,ya)
        ax[0].annotate(e, xy = xya, xytext=xy, color = colors[ci],
                       arrowprops=dict(arrowstyle="-", connectionstyle="arc3"))
####

        print e, fit_dict['name'], fit_dict['popt'], np.sqrt(-0.5 * fit_dict['popt'][0]), np.sum(chisqr) / (1.0*np.size(fit_dict['norm_y'][select]))
        ci = ci + 1
        if ci >= np.size(colors):
            ci = 0
            li = li + 1

    for i in [0,1]:
        ax[i].set_xlim(-14, -1.5)
        ax[i].set_ylim(1.0E-5, 9.0)
        ax[i].semilogy()
    ax[1].set_ylim(0.01, 10.0)

    ax[0].set_ylabel('Peak Normalized PDF from Data')
    ax[1].set_ylabel('Peak Normalized PDF from Fit')

    fig.subplots_adjust(hspace = 0)
    plt.setp([a.get_xticklabels() for a in fig.axes[:-1]], visible = False)
    plt.minorticks_on()

    fig.savefig(dsname + '_' + phase + '_all_elements_fit.png')
    plt.close()

    return


def plot_phase_panel(data, dsname, elements = None, **kwargs):

    phases = ['Molecular','CNM','WNM','WIM','HIM','Disk']

    if elements is None:
        elements = ['Ba','Y','As','Sr','Mn','Na','Ca','N','Ni','Mg','S','Si','Fe','C','O']

    elements = ['Ba', 'Sr', 'Fe', 'Mn', 'Mg', 'O', 'N']
    #elements = ['Mg','O']
    fig, ax = plt.subplots(3,2)
    fig.set_size_inches(36,6*3)

    bins    = data[dsname][phases[0]]['mass_fraction']['bins']
    centers = 0.5 * (bins[1:]+ bins[:-1])


#    sort   = np.argsort(ymax_order)
#    sort_e = np.array(elements)[sort]

    label_pos = np.empty((np.size(elements),))
    label_pos[::2] = 1
    label_pos[1::2] = -1

#    label_pos = label_pos[sort]

    ax_indexes = [(0,0),(0,1), (1,0), (1,1), (2,0), (2,1)]
    for axi, phase in enumerate(phases):
        ci = li = 0

        axi = ax_indexes[axi]
        for i, e in enumerate(elements):
            field = e + '_Fraction'

            ds_data = load_distribution_data(data, dsname, phase, field, centers = centers) # subselect

            fit_dict = fit_multifunction_PDF(1.0*bins, 1.0*ds_data['hist'], ds_data)
                   #fit_PDF(bins, ds_data['hist'], data = ds_data, **kwargs)


            plot_histogram(ax[axi], np.log10(bins), fit_dict['norm_y']/np.max(fit_dict['norm_y']),
                                        color = colors[ci], ls = lss[li], lw = line_width)

            ax[axi].plot(np.log10(centers),
                       #np.log10(fit_dict['fit_x']), 
                       fit_dict['fit_result'](centers) / np.max(fit_dict['norm_y']),
                                          lw = line_width, ls = '--', color = colors[ci])

####
            xtext = np.log10(centers[np.argmax(fit_dict['norm_y'])]) - 0.1 - 0.05
            xa    = np.log10(centers[np.argmax(fit_dict['norm_y'])])
            ya    = 1.0
            pos = label_pos[i]
            if pos > 0:
                xtext = xtext + 0.05
                ytext = 2.0
            xy = (xtext, ytext)
            xya = (xa,ya)
            ax[axi].annotate(e, xy = xya, xytext=xy, color = colors[ci],
                           arrowprops=dict(arrowstyle="-", connectionstyle="arc3"))
####

            if fit_dict['name'] == 'lognormal_powerlaw':
                N = fit_dict['fit_function'].N
            else:
                N = 0
            print phase, e, fit_dict['name'], fit_dict['popt'], "%5.5E"%(N)
            ci = ci + 1
            if ci >= np.size(colors):
                ci = 0
                li = li + 1

    for i, axi in enumerate(ax_indexes):
        ax[axi].set_xlim(-14, -1.5)
        ax[axi].set_ylim(1.0E-5, 9.0)
        ax[axi].semilogy()
        xy = (-3.0,1.0)
        ax[axi].annotate(phases[i], xy = xy, xytext=xy)

    for i in [0,1,2]:
        ax[(i,0)].set_ylabel('Peak Normalized PDF')       
        plt.setp( ax[(i,1)].get_yticklabels(), visible = False)
    #ax[1].set_ylim(0.01, 10.0)
    for i in [0,1]:
        ax[(2,i)].set_xlabel('log(Z)')         

    #ax[1].set_ylabel('Peak Normalized PDF')

    fig.subplots_adjust(hspace = 0, wspace = 0)
   # plt.setp([a.get_yticklabels() for a in fig.axes[1:]], visible = False)
    plt.minorticks_on()

    fig.savefig(dsname + '_multiphase_all_elements_fit.png')
    plt.close()

    return

def plot_phase_abundance_panel(data, dsname, elements = None, denominator = 'H', **kwargs):
    
    
    phases = ['Molecular','CNM','WNM','WIM','HIM','Disk']

    if elements is None:
        elements = ['Ba','Y','As','Sr','Mn','Na','Ca','N','Ni','Mg','S','Si','Fe','C','O']

    elements = ['Ba', 'Sr', 'Fe', 'Mn', 'Mg', 'O', 'N']
    #elements = ['Mg','O']
    fig, ax = plt.subplots(3,2)
    fig.set_size_inches(36,6*3)

    bins    = data[dsname][phases[0]]['mass_fraction']['abins']
    centers = 0.5 * (bins[1:]+ bins[:-1])


#    sort   = np.argsort(ymax_order)
#    sort_e = np.array(elements)[sort]

    label_pos = np.empty((np.size(elements),))
    label_pos[::2] = 1
    label_pos[1::2] = -1

#    label_pos = label_pos[sort]

    ax_indexes = [(0,0),(0,1), (1,0), (1,1), (2,0), (2,1)]
    for axi, phase in enumerate(phases):
        ci = li = 0

        axi = ax_indexes[axi]
        for i, e in enumerate(elements):
            if e == denominator:
                continue
            field = e + '_over_' + denominator

            ds_data = load_distribution_data(data, dsname, phase, field, centers = centers) # subselect

            #fit_dict = fit_multifunction_PDF(1.0*bins, 1.0*ds_data['hist'], ds_data)
                   #fit_PDF(bins, ds_data['hist'], data = ds_data, **kwargs)

            yplot = np.cumsum(ds_data['hist'])  / (1.0*np.sum(ds_data['hist']))
            binsize = (10**(bins[1:]) - 10**(bins[:-1]))
            yplot = ds_data['hist'] / binsize

#            select = yplot > 0
#            xplot = bins[select]
#            yplot = yplot[select]

            plot_histogram(ax[axi], bins, yplot / np.max(yplot), #fit_dict['norm_y']/np.max(fit_dict['norm_y']),
                                        color = colors[ci], ls = lss[li], lw = line_width, label = e)

            #ax[axi].plot(np.log10(centers),
                       #np.log10(fit_dict['fit_x']), 
            #           fit_dict['fit_result'](centers) / np.max(fit_dict['norm_y']),
            #                              lw = line_width, ls = lss[li], color = colors[ci])

####
            xtext = np.log10(centers[np.argmax(ds_data['hist'])]) - 0.1 - 0.05
            xa    = np.log10(centers[np.argmax(ds_data['hist'])])
            ya    = 1.0
            pos = label_pos[i]
            if pos > 0:
                xtext = xtext + 0.05
                ytext = 2.0
            xy = (xtext, ytext)
            xya = (xa,ya)
#            ax[axi].annotate(e, xy = xya, xytext=xy, color = colors[ci],
#                           arrowprops=dict(arrowstyle="-", connectionstyle="arc3"))
####

            print phase, e, # fit_dict['name'], fit_dict['popt']
            ci = ci + 1
            if ci >= np.size(colors):
                ci = 0
                li = li + 1

    for i, axi in enumerate(ax_indexes):

        if denominator == 'H':
            ax[axi].set_xlim(-8,0)
        else:
            ax[axi].set_xlim(-3,3)
        ax[axi].set_ylim(1.0E-5, 5.0)
        ax[axi].semilogy()
        xy = (-3.0,1.0)
        ax[axi].annotate(phases[i], xy = xy, xytext=xy)

    ax[(0,0)].legend(loc = 'upper right')
    for i in [0,1,2]:
        ax[(i,0)].set_ylabel('Peak Normalized PDF')       
        plt.setp( ax[(i,1)].get_yticklabels(), visible = False)
    #ax[1].set_ylim(0.01, 10.0)
    for i in [0,1]:
        ax[(2,i)].set_xlabel('[X/' + denominator + ']')         

    #ax[1].set_ylabel('Peak Normalized PDF')

    fig.subplots_adjust(hspace = 0, wspace = 0)
   # plt.setp([a.get_yticklabels() for a in fig.axes[1:]], visible = False)
    plt.minorticks_on()

    fig.savefig(dsname + '_multiphase_elements_over_' + denominator + '.png')
    plt.close()

    return



if __name__ == '__main__':
    """
    Runs the analysis and plots a full panel of all phases and
    the full disk for selected elements. Additional arguments
    to run are:
       1) ds_number
       2) ds_number_start ds_number_end  (assume go up by 1)
       3) ds_number_start ds_number_end di

    e.x. To run starting with DD0400 to DD0500 going up by 5:
        $python ./PDF.py 400 500 5
    """


    if len(sys.argv) == 1:
        all_ds = ["DD0400"]
    elif len(sys.argv) == 2:
        all_ds = ["DD%0004i"%(int(sys.argv[1]))]
    elif len(sys.argv) == 3 or len(sys.argv) == 4:

        if len(sys.argv) == 4:
            di = int(sys.argv[3])
        else:
            di = 1

        all_ds = ["DD%0004i"%(x) for x in np.arange( int(sys.argv[1]),
                                                     int(sys.argv[2])+di/2.0, di)]

    individual_fail = False
    gas_file = 'gas_abundances_ratios.h5'
    try:
        data = {all_ds[0] : dd.io.load(gas_file, "/" + all_ds[0]) }
    except:
        individual_fail = True
        all_data = dd.io.load(gas_file)

    for dsname in all_ds:
        print "Beginning on " + dsname

        if individual_fail:
            data = {dsname : all_data[dsname]}
        else:
            data = {dsname : dd.io.load(gas_file, "/" + dsname) }

#        plot_phase_panel(data, dsname)

#        dsarray = ["DD%0004i"%(x) for x in [100,500]] #np.arange(50, 555, 250)]
#        plot_time_evolution(gas_file, dsarray, denominator = None)


        if True:
             plot_phase_abundance_panel(data, dsname, denominator = 'Fe')
#            plot_phase_abundance_panel(data, dsname, denominator = 'Mg')
#            plot_phase_abundance_panel(data, dsname, denominator = 'O')


        if False:
            plot_all_elements(data, dsname, 'Molecular', function_to_fit = 'lognormal_powerlaw') #'lognormal_powerlaw')
            plot_all_elements(data, dsname, 'CNM', function_to_fit = 'lognormal_powerlaw') #'lognormal_powerlaw')
            plot_all_elements(data, dsname, 'WNM', function_to_fit = 'lognormal_powerlaw') #'lognormal_powerlaw')
            plot_all_elements(data, dsname, 'WIM', function_to_fit = 'lognormal_powerlaw') #'lognormal_powerlaw')
            plot_all_elements(data, dsname, 'HIM', function_to_fit = 'lognormal_powerlaw') #'lognormal_powerlaw')
            plot_all_elements(data, dsname, 'Disk', function_to_fit = 'lognormal_powerlaw') #'lognormal_powerlaw')

