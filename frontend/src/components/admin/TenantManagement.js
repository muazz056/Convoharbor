import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import tenantService from '../../services/tenant.service';

const TenantManagement = () => {
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const [selectedTenant, setSelectedTenant] = useState(null);
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
    const [formData, setFormData] = useState({
        name: '',
        domain: '',
        type: 'managed',
        admin_email: '',
        admin_password: ''
    });
    
    // Fetch tenants
    const { data: tenantsData, isLoading } = useQuery(
        'tenants',
        () => tenantService.getTenants(),
        {
            enabled: user?.role === 'super_admin'
        }
    );
    
    // Create tenant mutation
    const createTenant = useMutation(
        (data) => tenantService.createTenant(data),
        {
            onSuccess: () => {
                queryClient.invalidateQueries('tenants');
                setIsCreateModalOpen(false);
                setFormData({
                    name: '',
                    domain: '',
                    type: 'managed',
                    admin_email: '',
                    admin_password: ''
                });
            }
        }
    );
    
    // Update tenant mutation
    const updateTenant = useMutation(
        ({ tenantId, updates }) => tenantService.updateTenant(tenantId, updates),
        {
            onSuccess: () => {
                queryClient.invalidateQueries('tenants');
                setSelectedTenant(null);
            }
        }
    );
    
    const handleSubmit = (e) => {
        e.preventDefault();
        createTenant.mutate(formData);
    };
    
    const handleUpdate = (tenant, updates) => {
        updateTenant.mutate({ tenantId: tenant.id, updates });
    };
    
    if (!user?.role === 'super_admin') {
        return <div>Access Denied</div>;
    }
    
    if (isLoading) {
        return <div>Loading...</div>;
    }
    
    return (
        <div className="p-6">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800">Tenant Management</h1>
                    <p className="text-gray-600">Create and manage tenant accounts</p>
                </div>
                <button
                    onClick={() => setIsCreateModalOpen(true)}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                    Create New Tenant
                </button>
            </div>
            
            {/* Create Tenant Modal */}
            {isCreateModalOpen && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
                    <div className="bg-white rounded-xl p-6 w-full max-w-md">
                        <h2 className="text-xl font-semibold mb-4">Create New Tenant</h2>
                        <form onSubmit={handleSubmit}>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700">Name</label>
                                    <input
                                        type="text"
                                        value={formData.name}
                                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
                                        required
                                    />
                                </div>
                                
                                <div>
                                    <label className="block text-sm font-medium text-gray-700">Domain</label>
                                    <input
                                        type="text"
                                        value={formData.domain}
                                        onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
                                        required
                                    />
                                </div>
                                
                                <div>
                                    <label className="block text-sm font-medium text-gray-700">Type</label>
                                    <select
                                        value={formData.type}
                                        onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
                                    >
                                        <option value="managed">Managed</option>
                                        <option value="convopilot">ConvoPilot</option>
                                    </select>
                                </div>
                                
                                <div>
                                    <label className="block text-sm font-medium text-gray-700">Admin Email</label>
                                    <input
                                        type="email"
                                        value={formData.admin_email}
                                        onChange={(e) => setFormData({ ...formData, admin_email: e.target.value })}
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
                                        required
                                    />
                                </div>
                                
                                <div>
                                    <label className="block text-sm font-medium text-gray-700">Admin Password</label>
                                    <input
                                        type="password"
                                        value={formData.admin_password}
                                        onChange={(e) => setFormData({ ...formData, admin_password: e.target.value })}
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
                                        required
                                    />
                                </div>
                            </div>
                            
                            <div className="mt-6 flex justify-end gap-3">
                                <button
                                    type="button"
                                    onClick={() => setIsCreateModalOpen(false)}
                                    className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                                    disabled={createTenant.isLoading}
                                >
                                    {createTenant.isLoading ? 'Creating...' : 'Create Tenant'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
            
            {/* Tenants List */}
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
                <table className="w-full">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Domain</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                        {tenantsData?.tenants?.map(tenant => (
                            <tr key={tenant.id}>
                                <td className="px-6 py-4 font-medium text-gray-900">{tenant.name}</td>
                                <td className="px-6 py-4 text-gray-500">{tenant.domain}</td>
                                <td className="px-6 py-4">
                                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                                        tenant.type === 'convopilot'
                                            ? 'bg-blue-100 text-blue-800'
                                            : 'bg-purple-100 text-purple-800'
                                    }`}>
                                        {tenant.type}
                                    </span>
                                </td>
                                <td className="px-6 py-4">
                                    <select
                                        value={tenant.status}
                                        onChange={(e) => handleUpdate(tenant, { status: e.target.value })}
                                        className={`px-2 py-1 text-sm font-medium rounded-md ${
                                            tenant.status === 'active'
                                                ? 'bg-green-100 text-green-800'
                                                : 'bg-red-100 text-red-800'
                                        }`}
                                    >
                                        <option value="active">Active</option>
                                        <option value="suspended">Suspended</option>
                                        <option value="deleted">Deleted</option>
                                    </select>
                                </td>
                                <td className="px-6 py-4">
                                    <button
                                        onClick={() => setSelectedTenant(tenant)}
                                        className="text-indigo-600 hover:text-indigo-900"
                                    >
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

export default TenantManagement;
