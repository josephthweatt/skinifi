# Skinifi: Thinner NiFi Images for Docker

## About
Skinifi (skinny-nifi) is a python tool for creating NiFi images without unneeded artifacts or documentation.

NiFi's default image is currently a couple Gigabytes in size, largely due to the trove of useful libraries. However, 
this becomes a problem in environments where space is limited or when images are frequently moved around. 

A skinifi image by default is only 600 MB and contains only the artifacts needed to run. This tool also allows you
to specify the Process Groups you need to use and imports the processors needed for them to run.

## How to Use
If you want to create the base skinifi image without extra artifacts, run `python3 create_skinifi.py`

The image will be created and added to your local docker environment with the name **skinifi** (use --tag to customize)

Specifying additional artifacts can be done by adding either a template or Flow. `create_skinifi` will parse
these files for artifacts to include into the NiFi image.

### Adding a Template
1. Create a template using an existing NiFi instance. Learn how

2. Save the template as an xml and copy it to **templates/**

3. Running `create_skinifi` will automatically parse xml templates in this directory

### Adding a Flow from NiFi Registry
1. Create a file titled **registries.json** in the root directory (this one)

2. Create a Json object specifying the registry urls, bucket id, and the flow id you wish to use. 
    See **registries.json.example** for reference.
    
3. Running `create_skinifi` will automatically parse flows specified in **registries.json**

4. If you intend to download nar files from your NiFI Registry, you can set the `useBundles` attribute to true in
    the json file. See **registries.json.example** for reference.

**IMPORTANT:** If you are using custom processors in your flow you will need to add the nar file to **custom-processors/**
or have the nar files available as bundles in NiFi Registry. 

## Add Processors

### Adding Custom Processors
If you are using custom processors in your work, you will either need to add the nar files to 
**custom-processors/**, specify a path with the `--custom-nar-directory` flag, or set `useBundles` to true within the 
registries objects of **registries.json**
 
Nar files which are specified in either a template or Flow will be copied into the skinifi image.

Note: `create_skinifi` does not search **custom-processors** for nar files recursively. Avoid adding subdirectories
to here

### Adding Default Processors
By default, `create_skinifi` will download the required default processors from an online repository. If you want to use
a different path or url, set that with the ` --generic-nar-directory` flag.

Once downloaded, skinifi will save the processors to **skinifi-image/generic-nars/** for future use.

#### Prioritization of Processor Sources
Although multiple sources of processors may be specified, `create_skinifi` will only import one nar file of a single 
name and version. All other files of the same name will be ignored. Below is how `create_skinifi` prioritizes sources.

1. NiFi Registries: Specified in **registries.json**, will add the nar file from the first bucket it searches
2. Custom Nar Path: If not specified with `--custom-nar-directory`, it will check **custom-processors**
3. Saved Default Nars: A directory in skinifi-image that saves default processors downloaded from a remote repository.
4. Default Nars Path: Either a specified path, specified URL, or the default remote S3 bucket.
    
    Note: The remote S3 bucket is set up only for this project and is not maintained by the NiFi community. It is also 
    using the free version so requests may be limited. It is suggested you use a personal method of storage to avoid 
    inaccessibility to default processors.
