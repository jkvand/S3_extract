#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Snappy based functions
"""
import math

# Import SNAP libraries
from snappy import ProductIO, GeoPos, PixelPos, HashMap, GPF, jpy, Mask


def open_prod(inpath):
    """Open SNAP product.

     Use SNAP to open a Sentinel 3 product.

    Args:
        inpath (str): Path to a S3 OLCI image xfdumanisfest.xml file

    Returns:
        (java.lang.Object): snappy java object: SNAP image product
     """
    # Open satellite product with SNAP
    try:
        prod = ProductIO.readProduct(inpath)

    except IOError:
        print("Error: SNAP cannot read specified file!")

    return prod


def pixel_position(inprod, inlat, inlon):
    """Get pixel position in a product.

    Extract the pixel position from a product, based on lat / lon coordinates.

    Args:
        inprod (java.lang.Object): SNAP image product
        inlat (float): latitude of the coordinate in degrees EPSG:4326
        inlon (float): longitude of the coordinate in degrees EPSG:4326

    Returns:
        (tuple): pixel coordinates xx: (int), yy: (int). Returns "None" if\
                 pixel is out of bounds.
    """

    # Read lat/lon position into a GeoPos item
    gpos = GeoPos(inlat, inlon)

    # Retrieve pixel position of lat/lon values
    pixpos = inprod.getSceneGeoCoding().getPixelPos(gpos, PixelPos())

    # If the pixpos coordinates are NaN, the queried position is outside of the
    # image bands
    if math.isnan(pixpos.getX()) or math.isnan(pixpos.getY()):
        xx = None
        yy = None

    else:

        # Get pixel position in the product and retrieve pixel position of
        # lat/lon values.
        xx = int(pixpos.getX())
        yy = int(pixpos.getY())

    return (xx, yy)


def subset(inprod, inlat, inlon, subset_size=3, copyMetadata="true"):
    """Subset a S3 scene opened in snappy around lat lon coordinates.

    Create a subset of the given product around the point of interest. The
     subset is 3x3 pixels, and returns the pixel positions of the coordinates
     for the subset.

     Args:
        inprod (java.lang.Object): snappy java object: SNAP image product
        inlat (float): latitude of the coordinate in degrees EPSG:4326
        inlon (float): longitude of the coordinate in degrees EPSG:4326
        subset_size (int): size of the x by x window to subset. Default = 3.
        copyMetadata (bool): flag to copy Metadata in the output product, true\
                             by default.

    Returns:
        (tuple): tuple containing:
            prod_subset (java.lang.Object): snappy 3x3 subset around coordinate
            subx, suby (tuple): pixel coordinates: xx, yy.
    """
    # Get pixel position in the product and retrieve x,y.
    xx, yy = pixel_position(inprod, inlat, inlon)

    # Subset around point
    area = [
        xx - subset_size,
        yy - subset_size,
        subset_size * 2,
        subset_size * 2,
    ]

    # Empty HashMap
    parameters = HashMap()

    # Convert area list to string readable by the processor
    areastr = ",".join(str(e) for e in area)

    # Subset parameters
    parameters.put("region", areastr)
    parameters.put("subSamplingX", "1")
    parameters.put("subSamplingY", "1")
    parameters.put("copyMetadata", copyMetadata)

    # Create subset using operator
    prod_subset = GPF.createProduct("Subset", parameters, inprod)

    # Get pixel position in the subset (and therefore other products)
    subx, suby = pixel_position(prod_subset, inlat, inlon)

    return prod_subset, (subx, suby)


def rad2refl(
    inprod,
    sensor="OLCI",
    mode="RAD_TO_REFL",
    tpg="False",
    flags="False",
    nonspec="False",
):
    """ Radiance to Reflectance.

    Convert a Sentinel 3 OLCI L1C radiance bands to TOA reflectance.

     Args:
        inprod (java.lang.Object): snappy java object: SNAP image product
        sensor (str): satellite sensor that produced the input scene
        tpg (str): include or not the TiePointGrids in output
        flags (str): include or not the Product flags in output
        nonspec (str): include or not the non spectral bands in output

    Returns:
        toa_refl (java.lang.Object): snappy TOA reflectance product
    """

    # Empty HashMap
    parameters = HashMap()

    # Put parameters for snow albedo processor
    parameters.put("sensor", sensor)
    parameters.put("conversionMode", mode)
    parameters.put("copyTiePointGrids", tpg)
    parameters.put("copyFlagBandsAndMasks", flags)
    parameters.put("copyNonSpectralBands", nonspec)

    toa_refl = GPF.createProduct("Rad2Refl", parameters, inprod)

    return toa_refl


def snap_snow_albedo(
    inprod,
    pollution_flag,
    pollution_delta,
    gains,
    ndsi_flag="false",  # NDSI flag
    ndsi_thres="0.03",  # NDSI threshold
    pollution_params="false",  # Write pollution parameters
    pollution_uncertainties="false",  # Write pollution uncert
    deltabrr="0.01",  # Delta rBRR for uncertainties
    ppa_flag="false",  # Calculate PPA
    copyrefl="true",  # Copy rBRR bands to product
    refwvl="1020.0",  # Reference wvl for albedo calculation
    cloud_mask_name="cloud_over_snow",
):
    """Snow Albedo Processor v2.0.9

        Run the S3 SNOW processor on the snappy product with the provided
        options and return the snappy albedo product.

        Args:
            inprod (java.lang.Object): snappy java object: SNAP image product
            pollution_flag (bool): S3 SNOW dirty snow flag
            pollution_delta (int): Delta value to consider dirty snow
            gains (bool): Consider vicarious calibration gains
            ndsi_flag (bool):
            ndsi_thres (str):
            pollution_params (bool):
            pollution_uncertainties (bool):
            deltabrr (str):
            ppa_flag
            copyrefl
            refwvl
            cloud_mask_name (str): specify the name of the cloud mask if it \
                                   exists


        Returns:
            (java.lang.Object): snappy object"""
    # Set gain values and run processor
    if gains:
        gain_b1 = "0.9798"
        gain_b5 = "0.9892"
        gain_b17 = "1"
        gain_b21 = "0.914"
    else:
        gain_b1 = "1"
        gain_b5 = "1"
        gain_b17 = "1"
        gain_b21 = "1"

    # Empty HashMap
    parameters = HashMap()

    # Parameters for snow albedo processor
    # Cloud mask name
    parameters.put("cloudMaskBandName", cloud_mask_name)

    # Consider NDSI mask
    parameters.put("considerNdsiSnowMask", ndsi_flag)

    # NDSI threshold
    parameters.put("ndsiThresh", ndsi_thres)

    # Consider snow pollution
    parameters.put("considerSnowPollution", pollution_flag)
    parameters.put("pollutionDelta", pollution_delta)
    parameters.put("writeAdditionalSnowPollutionParms", pollution_params)
    parameters.put(
        "writeUncertaintiesOfAdditionalSnowPollutionParms",
        pollution_uncertainties,
    )
    parameters.put("deltaBrr", deltabrr)

    # PPA
    parameters.put("computePPA", ppa_flag)

    # Reflectance
    parameters.put("copyReflectanceBands", copyrefl)

    # Select reference wvl to compute the albedo
    parameters.put("refWvl", refwvl)

    # Hard coded gains for band 1 and 21
    parameters.put("olciGainBand1", gain_b1)
    parameters.put("olciGainBand5", gain_b5)
    parameters.put("olciGainBand17", gain_b17)
    parameters.put("olciGainBand21", gain_b21)

    # Band list for output (for the moment hard code 21 bands)
    bandlist = (
        "Oa01 (400 nm),Oa02 (412.5 nm),Oa03 (442.5 nm),Oa04 (490 nm),"
        "Oa05 (510 nm),Oa06 (560 nm),Oa07 (620 nm),Oa08 (665 nm),Oa09"
        " (673.75 nm),Oa10 (681.25 nm),Oa11 (708.75 nm),Oa12 (753.75 "
        "nm),Oa13 (761.25 nm),Oa14 (764.375 nm),Oa15 (767.5 nm),Oa16 "
        "(778.75 nm),Oa17 (865 nm),Oa18 (885 nm),Oa19 (900 nm),Oa20 ("
        "940 nm),Oa21 (1020 nm)"
    )

    parameters.put("spectralAlbedoTargetBands", bandlist)

    # Run the Albedo computation
    albedo = GPF.createProduct("OLCI.SnowProperties", parameters, inprod)

    return albedo


def idepix_cloud(in_prod, xpix, ypix):
    """ Run the experimental cloud over snow processor and return
        a flag. 1 = probable cloud, 0 = no cloud """
    parameters = HashMap()
    parameters.put("demBandName", "band_1")
    idepix_cld = GPF.createProduct(
        "Snap.Idepix.Olci.S3Snow", parameters, in_prod
    )
    cloudband = idepix_cld.getBand("cloud_over_snow")
    cloudband.loadRasterData()

    return cloudband.getPixelInt(xpix, ypix)


def dem_extract(in_prod, xpix, ypix, bandname="altitude"):
    """Run the S3 SNOW DEM tool.

    Args:
        inprod (java.lang.Object): snappy java object: SNAP image product
        xpix (float): x position in product to query
        ypix (float): y position in product to query
        bandname (str): DEM band name in product

    Returns:
        slope_vals (dictionnary): values from all bands at the given x,y"""

    # Initialise a HashMap
    parameters = HashMap()

    parameters.put("elevationBandName", bandname)
    parameters.put("copyElevationBand", "true")

    # Run slope operator
    s3snow_slope = GPF.createProduct("SlopeCalculation", parameters, in_prod)

    # Initialise dictionnary to store data
    slope_vals = {}

    # Get all bands
    for band in list(s3snow_slope.getBandNames()):
        currentband = s3snow_slope.getBand(band)
        currentband.loadRasterData()
        slope_vals[band] = currentband.getPixelFloat(xpix, ypix)

    return slope_vals


def getTiePointGrid_value(inprod, tpg_name, xx, yy):

    tpg = inprod.getTiePointGrid(tpg_name)
    tpg.readRasterDataFully()

    return tpg.getPixelFloat(yy, xx)


def merge2dicts(x, y):
    """Merge two dictionnaries

    Merges two existing dictionnaries, returning a new one.

    Args:
        x (dict): First dictionnary to merge
        y (dict): Second dictionnary to merge

    Returns:
        (dict): Merged dictionnary"""

    z = x.copy()  # start with x's keys and values
    z.update(y)  # modifies z with y's keys and values & returns None

    return z


def get_valid_mask(xx, yy, prod):

    valid_mask = prod.getMaskGroup().get("quality_flags_invalid")

    valid_mask_asmask = jpy.cast(valid_mask, Mask)

    return valid_mask_asmask.getSampleInt(xx, yy)


def getS3values(
    in_file,
    coords,
    snow_pollution,
    pollution_delta,
    gains,
    dem_prods,
    errorfile,
):
    """Extract data from S3 SNOW.

    Read the input S3 file and run the S3 OLCI SNOW processor for the
    coordinates located within the scene.

    Args:
        in_file (str): Path to a S3 OLCI image xfdumanisfest.xml file
        coords (list): List of coordinates to extract the data from
        pollution (bool): S3 SNOW dirty snow flag
        delta_pol (int): Delta value to consider dirty snow in S3 SNOW
        gains (bool): Consider vicarious calibration gains
        dem_prods (bool): Run the S3 Snow DEM slope plugin
        """
    # Make a dictionnary to store results
    stored_vals = {}

    # Open SNAP product
    prod = open_prod(in_file)

    # Loop over coordinates to extract values.
    for coord in coords:

        # Check if data exists at the queried location
        # Transform lat/lon to position to x, y in scene
        xx, yy = pixel_position(prod, coord[1], coord[2])

        # Test if the pixel is valid (in the scene and not in the image border)
        try:
            mask = get_valid_mask(xx, yy, prod)
        except:  # Bare except needed to catch the JAVA exception
            mask = 255

        # Log if location is outside of file
        if not xx or not yy:
            pass
        # Log if coordinate is in file but invalid pixel
        elif mask == 255:
            with open(str(errorfile), "a") as fd:
                fd.write(
                    "%s, %s: Invalid pixel.\n" % (prod.getName(), coord[0])
                )
        else:

            # Save resources by working on a small subset around each
            # coordinates pair contained within the S3 scene. Doesn't process
            # if the coordinates pair is not in the product
            try:
                prod_subset, pix_coords = subset(prod, coord[1], coord[2])

                if not prod_subset or not pix_coords[0]:
                    out_values = None  # None if location not in product
                    prod_subset = None  # None to stop processing
                    with open(str(errorfile), "a") as fd:
                        fd.write(
                            "%s, %s: Unable to subset,"
                            " too close to the edge.\n"
                            % (prod.getName(), coord[0])
                        )

            except:  # Bare except needed to catch the JAVA exception
                with open(str(errorfile), "a") as fd:
                    fd.write(
                        "%s, %s: Corrupt file or"
                        " SNAP issue.\n" % (prod.getName(), coord[0])
                    )
                prod_subset = None  # Set a marker to ignore rest of processing

            if prod_subset:  # Run the processing if subset exists

                # Fetch the TOA reflectance for the image
                toa_refl = rad2refl(prod_subset)

                # Run the S3 OLCI SNOW processor on the subset
                snap_albedo = snap_snow_albedo(
                    prod_subset, snow_pollution, pollution_delta, gains
                )

                # Extract values from albedo product
                out_values = {
                    "grain_diameter": None,
                    "ndbi": None,
                    "ndsi": None,
                    "snow_specific_area": None,
                }

                # Add band names to extract to the dictionnary
                rbrr_bands = [
                    x for x in list(snap_albedo.getBandNames()) if "BRR" in x
                ]
                planar_bands = [
                    x
                    for x in list(snap_albedo.getBandNames())
                    if "spectral_planar" in x
                ]
                bb_bands = [
                    x
                    for x in list(snap_albedo.getBandNames())
                    if "albedo_bb" in x
                ]
                alb_bands = rbrr_bands + planar_bands + bb_bands
                for item in alb_bands:
                    out_values.update({item: None})

                # Update albedo values
                for key in out_values:
                    item = next(
                        x for x in list(snap_albedo.getBandNames()) if key in x
                    )
                    currentband = None
                    currentband = snap_albedo.getBand(item)
                    currentband.loadRasterData()
                    out_values[key] = round(
                        currentband.getPixelFloat(
                            pix_coords[0], pix_coords[1]
                        ),
                        4,
                    )

                # Read geometry from the tie point grids
                vza = getTiePointGrid_value(
                    prod_subset, "OZA", pix_coords[0], pix_coords[1]
                )
                vaa = getTiePointGrid_value(
                    prod_subset, "OAA", pix_coords[0], pix_coords[1]
                )
                saa = getTiePointGrid_value(
                    prod_subset, "SAA", pix_coords[0], pix_coords[1]
                )
                sza = getTiePointGrid_value(
                    prod_subset, "SZA", pix_coords[0], pix_coords[1]
                )

                # Update geometry
                out_values.update(
                    {"sza": sza, "vza": vza, "vaa": vaa, "saa": saa}
                )

                # Get TOA Reflectance and update dictionnary
                toa_refl_bands = list(toa_refl.getBandNames())
                for bnd in toa_refl_bands:
                    currentband = None
                    currentband = toa_refl.getBand(bnd)
                    currentband.loadRasterData()
                    out_values.update(
                        {
                            bnd: round(
                                currentband.getPixelFloat(
                                    pix_coords[0], pix_coords[1]
                                ),
                                4,
                            )
                        }
                    )

                # Add experimental cloud over snow result
                out_values.update(
                    {
                        "auto_cloud": idepix_cloud(
                            prod_subset, pix_coords[0], pix_coords[1]
                        )
                    }
                )
                # Run the DEM product as an options
                if dem_prods:
                    dem_values = dem_extract(
                        prod_subset, pix_coords[0], pix_coords[1]
                    )
                    # Merge DEM dictionnary
                    out_values = merge2dicts(out_values, dem_values)

                # Update the full dictionnary
                stored_vals.update({coord[0]: out_values})

                # Garbage collector
                prod_subset.dispose()
                snap_albedo.dispose()
                toa_refl.dispose()

    # Log if no sites are found in image
    if not stored_vals:
        with open(str(errorfile), "a") as fd:
            fd.write("%s: No sites in image.\n" % (prod.getName()))

    # Garbage collector
    prod.dispose()

    return stored_vals
