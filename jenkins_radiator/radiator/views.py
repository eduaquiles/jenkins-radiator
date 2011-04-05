from django.shortcuts import render_to_response as render
from django.conf import settings
import models
import re

# Create your views here.
def avg(lst):
    return sum(lst) / (1.0 * len(lst))


def get_radiator(request, build_list):
    buildCount = request.GET.get('builds',settings.HUDSON_BUILD_COUNT)
    build_types = [build_row.split(',') for build_row in build_list.split('|')]
    columnSize = 100 / len(build_types[0])
    return render('radiator/builds.html', locals())

def get_builds(request, build_type):
    count = int(request.GET.get('builds',settings.HUDSON_BUILD_COUNT))    
    builds = models.get_recent_builds( build_type + settings.HUDSON_BUILD_NAME_PATTERN, count )
    buildDict = lookupTests(build_type, count, builds)

    avgTime = avg([build.duration for build in builds])
    if builds[0].status == 'BUILDING':
        progBarDone = (builds[0].runningTime / avgTime) * 100
        progBarLeft = 100 - progBarDone
    
    return render('radiator/builds_table.html', locals())

def get_build_info(request, build_type, build_number):
    build = models.get_specific_build(build_type+'_Build', build_number)
    buildDict = lookupTests(build_type, 20, [build])
    return render('radiator/build_detail.html', locals())
            
def lookupTests(build_type, count, builds):
    project = models.Project(build_type)

    testProjects = models.get_test_projects(models.get_data(settings.HUDSON_URL + '/api/json?tree=jobs[name]'), build_type)
    testProjects = [proj for proj in testProjects if not settings.HUDSON_TEST_IGNORE_REGEX.findall(proj)]
    project.smokeTests = [proj for proj in testProjects if settings.HUDSON_SMOKE_NAME_REGEX.findall(proj) ]
    project.otherTests = [proj for proj in testProjects if not settings.HUDSON_SMOKE_NAME_REGEX.findall(proj) ]

    buildDict = dict((build.number,build) for build in builds)

    smokeBuilds = []
    for testName in project.smokeTests:
        smokeBuilds.extend(models.get_recent_builds( testName, count ))

    regressionBuilds = []
    for testName in project.otherTests:
        regressionBuilds.extend(models.get_recent_builds( testName, count  ))

    for test in smokeBuilds:
        parent = buildDict.get(test.parent)
        if parent is not None:
            if test.project not in parent.smokeTests or int(test.number) > int(parent.smokeTests[test.project].number):
                parent.smokeTests[test.project] = test

    for test in regressionBuilds:
        parent = buildDict.get(test.parent)
        if parent is not None:
            if test.project not in parent.regressionTests or int(test.number) > int(parent.regressionTests[test.project].number):
                parent.regressionTests[test.project] = test
    
    for build in builds:
        for smoke in project.smokeTests:
            if smoke not in build.smokeTests:
                build.smokeTests[smoke]= models.Build(projectName=smoke)
    
        for other in project.otherTests:
            if other not in build.regressionTests:
                build.regressionTests[other]= models.Build(projectName=other)
    
    return buildDict

def get_test_report(request, test_name):
    count = int(request.GET.get('builds',settings.HUDSON_BUILD_COUNT))
    tests = models.get_recent_builds( test_name, count )
    caseDict = {}
    for test in tests:
        if test.testCases:
            for case in test.testCases:
                caseTuple = caseDict.get(case.name,(0,[]))
                errorCount = caseTuple[0]
                caseList = caseTuple[1]
                caseList.extend([case])
                if case.status in ['FAILED','REGRESSION']:
                    errorCount = errorCount + 1
                caseDict.update({case.name:(errorCount,caseList)})

    summary = []
    for k, v in caseDict.iteritems():
        triple = (k,v[0],v[1])
        summary.append(triple)
    
    summary = sorted(summary, key=lambda c: c[1], reverse=True)
    return render('radiator/test_report.html', locals())
