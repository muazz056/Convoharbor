import React from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useQuery } from 'react-query';
import tenantService from '../../services/tenant.service';

const AdminDashboard = () => {
    const { user } = useAuth();
    
    // Fetch tenants data
    const { data: tenantsData, isLoading: tenantsLoading } = useQuery(
        'tenants',
        () => tenantService.getTenants(),
        {
            enabled: user?.role === 'super_admin'
        }
    );
    
    if (!user?.role === 'super_admin') {
        return <div>Access Denied</div>;
    }
    
    if (tenantsLoading) {
        return <div>Loading...</div>;
    }
    
    return (
        <div className="p-6">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-gray-800">Admin Dashboard</h1>
                <p className="text-gray-600">Manage tenants and system settings</p>
            </div>
            
            {/* Stats Overview */}
            <div className="grid grid-cols-4 gap-4 mb-6">
                <div className="bg-white rounded-xl p-6 shadow-sm">
                    <h3 className="text-lg font-semibold mb-2">Total Tenants</h3>
                    <p className="text-3xl font-bold text-indigo-600">
                        {tenantsData?.total || 0}
                    </p>
                </div>
                
                <div className="bg-white rounded-xl p-6 shadow-sm">
                    <h3 className="text-lg font-semibold mb-2">Active Tenants</h3>
                    <p className="text-3xl font-bold text-green-600">
                        {tenantsData?.tenants?.filter(t => t.status === 'active').length || 0}
                    </p>
                </div>
                
                <div className="bg-white rounded-xl p-6 shadow-sm">
                    <h3 className="text-lg font-semibold mb-2">Total Users</h3>
                    <p className="text-3xl font-bold text-blue-600">
                        {tenantsData?.totalUsers || 0}
                    </p>
                </div>
                
                <div className="bg-white rounded-xl p-6 shadow-sm">
                    <h3 className="text-lg font-semibold mb-2">Total Revenue</h3>
                    <p className="text-3xl font-bold text-purple-600">
                        €{tenantsData?.totalRevenue || 0}
                    </p>
                </div>
            </div>
            
            {/* Tenants Table */}
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
                <div className="p-6 border-b border-gray-200">
                    <h2 className="text-xl font-semibold">Tenants</h2>
                </div>
                
                <table className="w-full">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Users</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                        {tenantsData?.tenants?.map(tenant => (
                            <tr key={tenant.id}>
                                <td className="px-6 py-4">
                                    <div>
                                        <div className="font-medium text-gray-900">{tenant.name}</div>
                                        <div className="text-sm text-gray-500">{tenant.domain}</div>
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                                        tenant.type === 'convoharbor'
                                            ? 'bg-blue-100 text-blue-800'
                                            : 'bg-purple-100 text-purple-800'
                                    }`}>
                                        {tenant.type}
                                    </span>
                                </td>
                                <td className="px-6 py-4">
                                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                                        tenant.status === 'active'
                                            ? 'bg-green-100 text-green-800'
                                            : 'bg-red-100 text-red-800'
                                    }`}>
                                        {tenant.status}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-gray-900">{tenant.userCount}</td>
                                <td className="px-6 py-4 text-gray-500">
                                    {new Date(tenant.created_at).toLocaleDateString()}
                                </td>
                                <td className="px-6 py-4">
                                    <button className="text-indigo-600 hover:text-indigo-900">
                                        Manage
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default AdminDashboard;
