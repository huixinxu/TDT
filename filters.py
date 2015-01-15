"""
:File: filters.py
:Author: Jack A. Kosmicki
:Last updated: 2014-12-01

File of filters for quality control of VCF files
Additional filters for determining Par regions
"""

from __future__ import division
import sys


def passFilters(stats, thresh, GQ_Thresh):
    """series of filters used to remove bad calls
        stats are the individuals values (GT:AD:DP:GQ:PL)
        AD: allelic depth
        DP: approximate number of reads that passed the filter
        GQ: genotype quality
        PL: phred scale score

        We allow case/controls, parents, and kids to have different GQ thresholds, 
        therefore to make a generic function GQ_Thresh is specified despite all 
        three GQ thresholds being located in the hash table 'thresh'
    """

    genotype = stats['GT']

    # ensure individual has a genotype
    if genotype == None:
        return False

    # genotype quality score must be >= GQ Threshold [default: 30]
    elif float(stats['GQ']) < GQ_Thresh:
        return False

    # read depth must be >= DP threshold [default: 10]
    elif float(stats['DP']) < thresh['DP_Thresh']:
        return False

    # Allele balance of <0.1 for homozygous Reference individuals
    elif genotype == 'homoRef':
        ABratio = AllelicBalance(stats['AD'])
        if ABratio >= thresh['AB_Ref_Thresh']:
            return False
        else:
            return True

    # Allele balance of between 0.3 and 0.7 for hets
    elif genotype == 'het':
        # calculate the allelic balance from the allelic depth
        ABratio = AllelicBalance(stats['AD'])
        if ABratio < thresh['AB_Het_Thresh'] or ABratio > (1-thresh['AB_Het_Thresh']):
            return False
        else:
            return True

    elif genotype == 'homoAlt':
        ABratio = AllelicBalance(stats['AD'])
        if ABratio <= thresh['AB_Alt_Thresh']:
            return False
        else:
            return True


def TDT_Parent_Filters(indiv, father, mother, thresh):
    """ Determine if parents have an alternate allele to pass on.
        
        Parameters
        ----------
        indiv = individual's ID
        family = dictionary containing the families
            key = child's ID 
            value = [Dad ID, Mom ID, sex]
        True = parents have alternate allele and passed filters
        False = parents don't have alternate allele or did not pass filters
    """

    # 1) find the parents' data 
    try:
        if father == None or mother == None:
            return False
        else:
            # Find the parent's GT:AD:DP:GQ:PL numbers
            dad_data, mom_data = father, mother

            dad_gtype, mom_gtype = dad_data['GT'], mom_data['GT']

            # determine the status of the phred Filter which will be either 
            # True (they passed) or False (they didn't pass)
            dad_Phred_Pass = PhredScaleFilter(dad_gtype, dad_data, thresh['PL_Thresh'])
            mom_Phred_Pass = PhredScaleFilter(mom_gtype, mom_data, thresh['PL_Thresh'])

            # 2) apply allelic balance filters to parents
            #    Both parents must pass all the filters
            if not passFilters(dad_data, thresh, thresh['GQ_Parent_Thresh']) or not passFilters(mom_data, thresh, thresh.get('GQ_Parent_Thresh')):
                return False

            # 3) apply PL filter to parents
            elif not dad_Phred_Pass or not mom_Phred_Pass:
                return False

            else:
                return True
    except KeyError:
        sys.stderr.write("KeyError with individual {}".format(indiv))
        return False


def AllelicBalance(AD):
    """ Calculate the allelic balance.
                                    alternate reads
        allelic balance = -----------------------------------
                           alternate reads + reference reads
    """
    
    ref = int(AD[0])
    alt = int(AD[1])

    return alt / (ref + alt)


def PhredScaleFilter(gtype, stats, PL_Thresh):
    """ This function determines what phred scale filter to use for
        a given individual as different genotypes require
        different filters
        Input: genotype, GT:AD:DP:GQ:PL values, the PL threshold
    """

    if gtype == 'homoRef':
        return PhredScaleFilter_HOMOREF(stats, PL_Thresh)
    elif gtype == 'het':
        return PhredScaleFilter_HET(stats, PL_Thresh)
    elif gtype == 'homoAlt':
        return PhredScaleFilter_HOMOALT(stats, PL_Thresh)
    else:
        return False


def PhredScaleFilter_HET(stats, PL_Thresh):
    """ Apply filters for the normalized Phred-scaled likelihoods for 
        AA, AB, BB genotypes where A = reference allele, B = alternate allele
        stats is the GT:AD:DP:GQ:PL scores
        True = Passed Filter
        False = Failed Filter
    """

    homoRef = int(stats['PL'][0])
    het = int(stats['PL'][1])
    homoAlt = int(stats['PL'][2])

    if homoRef < PL_Thresh:
        return False
    elif het != 0:
        return False
    elif homoAlt < PL_Thresh:
        return False
    else:
        return True


def PhredScaleFilter_HOMOREF(stats, PL_Thresh):
    """ Apply filters for the normalized Phred-scaled likelihoods for 
        AA, AB, BB genotypes where A = reference allele,
                                   B = alternate allele
        stats is the GT:AD:DP:GQ:PL scores
        True = Passed Filter
        False = Failed Filter
    """

    homoRef = int(stats['PL'][0])
    het = int(stats['PL'][1])
    homoAlt = int(stats['PL'][2])

    if homoRef != 0:
        return False
    elif het < PL_Thresh:
        return False
    elif homoAlt < PL_Thresh:
        return False
    else:
        return True


def PhredScaleFilter_HOMOALT(stats, PL_Thresh):
    """ Apply filters for the normalized Phred-scaled likelihoods for 
        AA, AB, BB genotypes where A = reference allele,
                                   B = alternate allele
        stats is the GT:AD:DP:GQ:PL scores
        True = Passed Filter
        False = Failed Filter
    """

    homoRef = int(stats['PL'][0])
    het = int(stats['PL'][1])
    homoAlt = int(stats['PL'][2])

    if homoAlt != 0:
        return False
    elif het < PL_Thresh:
        return False
    elif homoRef < PL_Thresh:
        return False
    else:
        return True


def check_Hemizgyous(chrom,gender,inParRegion):
    """ Hemizygous chromosomes have to be dealt with differently.

        Cases:
        Y is hemizgyous
        X is hemizygous in males if they aren't in the PAR region

        True: not in hemizygous case
        False: in a hemizgyous case
    """

    return chrom not in ('X','Y') or gender == 'female' or inParRegion


def inPar(pos):
    """ Are you in the pseudo-autosomal region (PAR)?
        True: in par               False: not in par

        Current PAR regions defined in GRCh37 from 
        http://www.ncbi.nlm.nih.gov/projects/genome/assembly/grc/human/
    """
    return (60001 <= pos <= 2699520) or (154931044 <= pos <= 155260560)
